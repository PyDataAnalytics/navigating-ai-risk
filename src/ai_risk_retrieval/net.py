"""
Network-safety helpers: URL vetting and secret redaction.

Single source of truth on purpose. The duplicated Ollama host validator in
config.py is how a weak check (`startswith("ollama")`) ended up in two places
and was fixed in only one; URL vetting lives here so there is one
implementation to review and one place to harden.

Two jobs:

1. ``safe_http_url`` — decide whether a URL is safe to fetch. Third parties
   supply URLs we later request: Unpaywall returns ``best_oa_location.url_for_pdf``,
   which the *publisher* controls, not Unpaywall. Without a check, a hostile or
   compromised record points the fetcher at cloud metadata
   (``169.254.169.254``), a loopback service (a local Ollama on 11434), or an
   internal address. http(s) only, no credentials, no literal private/loopback/
   link-local/reserved host.

2. ``redact_url`` / ``redact_exc`` — keep secrets out of logs. SerpApi only
   accepts its key as a query parameter, and httpx's ``raise_for_status``
   message embeds the full request URL, so ``log.warning(..., error=str(e))``
   writes the key to the log. Redact before logging.

DNS rebinding is out of scope: a hostname that resolves to a private address is
not caught here. ``require_resolved_public`` covers the fetch path, where the
cost of a resolve is acceptable.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Query-parameter names whose values are secrets or personal data. Matched
# case-insensitively as substrings, so `api_key`, `apikey` and `X-Api-Key` all hit.
_SENSITIVE_PARAM_HINTS = (
    "api_key",
    "apikey",
    "key",
    "token",
    "secret",
    "password",
    "passwd",
    "access_token",
    "auth",
    "signature",
    "sig",
    "email",
    "mailto",
)

_REDACTED = "REDACTED"

# Hostnames that are never a legitimate public fetch target.
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
        "instance-data",
    }
)


class UnsafeUrlError(ValueError):
    """Raised when a URL must not be fetched."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for any address we refuse to fetch from."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    # IPv4-mapped / translated IPv6 (e.g. ::ffff:127.0.0.1) would otherwise slip
    # past the checks above, which only inspect the IPv6 form.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None and _is_blocked_ip(mapped):
        return True
    for attr in ("sixtofour", "teredo"):
        embedded = getattr(ip, attr, None)
        if embedded is None:
            continue
        candidates = embedded if isinstance(embedded, tuple) else (embedded,)
        if any(_is_blocked_ip(c) for c in candidates):
            return True
    return False


def safe_http_url(value: object, *, field: str = "url") -> str:
    """
    Return ``value`` unchanged if it is a URL we are willing to fetch.

    Raises ``UnsafeUrlError`` otherwise. Checks, in order: it is a string; the
    scheme is http or https (so ``file:``, ``gopher:``, ``javascript:`` and the
    bare-prefix trick ``httpx://`` are all out); there are no embedded
    credentials; a host is present; and if the host is an IP literal, that it is
    not private, loopback, link-local, multicast, reserved or unspecified.
    """
    if not isinstance(value, str):
        raise UnsafeUrlError(f"{field}: expected a string URL, got {type(value).__name__}")
    url = value.strip()
    if not url:
        raise UnsafeUrlError(f"{field}: empty URL")
    if len(url) > 2000:
        raise UnsafeUrlError(f"{field}: URL longer than 2000 characters")

    try:
        parts = urlparse(url)
    except ValueError as exc:
        raise UnsafeUrlError(f"{field}: unparseable URL ({exc})") from exc

    if parts.scheme.lower() not in ("http", "https"):
        raise UnsafeUrlError(
            f"{field}: scheme {parts.scheme!r} is not http/https. "
            "A prefix test such as startswith('http') also admits 'httpx://'."
        )
    if parts.username or parts.password:
        raise UnsafeUrlError(f"{field}: URL carries embedded credentials")

    try:
        host = (parts.hostname or "").lower()
    except ValueError as exc:  # malformed IPv6 literal
        raise UnsafeUrlError(f"{field}: malformed host ({exc})") from exc
    if not host:
        raise UnsafeUrlError(f"{field}: URL has no host")
    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise UnsafeUrlError(f"{field}: host {host!r} is local")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url  # a hostname; resolution is the fetcher's job
    if _is_blocked_ip(ip):
        raise UnsafeUrlError(f"{field}: host {host!r} is a private or reserved address")
    return url


def is_safe_http_url(value: object) -> bool:
    """Boolean form of :func:`safe_http_url`."""
    try:
        safe_http_url(value)
    except UnsafeUrlError:
        return False
    return True


def require_resolved_public(url: str, *, field: str = "url") -> str:
    """
    As :func:`safe_http_url`, and additionally resolve the hostname and refuse
    the URL if any address it resolves to is private or reserved.

    Use on the fetch path. Not a complete defence against DNS rebinding — the
    name can resolve differently between this check and the request — but it
    stops the ordinary case of a hostname pointed at 127.0.0.1 or a metadata IP.
    """
    url = safe_http_url(url, field=field)
    host = urlparse(url).hostname or ""
    try:
        ipaddress.ip_address(host)
        return url  # literal, already vetted
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise UnsafeUrlError(f"{field}: cannot resolve host {host!r} ({exc})") from exc
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise UnsafeUrlError(
                f"{field}: host {host!r} resolves to private/reserved address {addr}"
            )
    return url


def redact_url(url: str) -> str:
    """Replace the values of sensitive query parameters with ``REDACTED``."""
    if not isinstance(url, str) or not url:
        return ""
    try:
        parts = urlparse(url)
    except ValueError:
        return _REDACTED
    if not parts.query:
        return url
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    cleaned = [
        (k, _REDACTED if any(h in k.lower() for h in _SENSITIVE_PARAM_HINTS) else v)
        for k, v in pairs
    ]
    return urlunparse(parts._replace(query=urlencode(cleaned)))


# Any http(s) URL appearing in free text (such as an exception message).
_URL_IN_TEXT = re.compile(r"https?://[^\s'\"<>|\\]+")


def redact_text(text: str) -> str:
    """Redact sensitive query parameters in every URL embedded in ``text``."""
    if not text:
        return ""
    return _URL_IN_TEXT.sub(lambda m: redact_url(m.group(0)), text)


def redact_exc(exc: BaseException) -> str:
    """
    ``str(exc)`` with secrets stripped from any URL it contains.

    httpx renders ``raise_for_status`` failures as
    ``Client error '429 ...' for url 'https://serpapi.com/search?...api_key=...'``,
    so logging ``str(e)`` directly publishes the key.
    """
    return redact_text(str(exc))
