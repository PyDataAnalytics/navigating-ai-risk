"""Tests for the shared URL-safety and redaction helpers (src/.../net.py)."""

import re
from urllib.parse import urlparse

import httpx
import pytest

from ai_risk_retrieval.net import (
    UnsafeUrlError,
    is_safe_http_url,
    redact_exc,
    redact_text,
    redact_url,
    safe_http_url,
)

# --- URLs a prefix test such as startswith("http") would admit -----------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",  # cloud metadata
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://127.0.0.1:11434/api/tags",  # the local Ollama the pipeline protects
        "http://[::1]:8080/admin",
        "http://[::ffff:127.0.0.1]/admin",  # IPv4-mapped loopback
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://0.0.0.0/",
        "http://foo.localhost/x",
        "httpx://not-a-scheme/x",  # prefix test admitted this
        "file:///etc/passwd",
        "http://user:pass@internal.svc/admin",  # embedded credentials
    ],
)
def test_unsafe_urls_rejected(url):
    assert not is_safe_http_url(url)
    with pytest.raises(UnsafeUrlError):
        safe_http_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://publisher.example.com/paper.pdf",
        "http://arxiv.org/pdf/2401.00001v1",
        "https://link.springer.com/content/pdf/10.1007%2Fx.pdf",
    ],
)
def test_public_urls_accepted(url):
    assert is_safe_http_url(url)
    assert safe_http_url(url) == url


def test_non_string_and_empty_rejected():
    for value in (None, 123, b"https://x.example", "", "   "):
        assert not is_safe_http_url(value)


def test_absurdly_long_url_rejected():
    assert not is_safe_http_url("https://example.com/" + "a" * 5000)


# --- redaction ---------------------------------------------------------------


def test_redact_exc_strips_serpapi_key():
    """httpx embeds the request URL in raise_for_status messages.

    google_scholar.py logs that message, so an unredacted str(e) publishes
    SERPAPI_API_KEY.
    """
    req = httpx.Request(
        "GET",
        "https://serpapi.com/search",
        params={"engine": "google_scholar", "q": "ai risk", "api_key": "SERPAPI-SECRET-abc123"},
    )
    with pytest.raises(httpx.HTTPStatusError) as caught:
        httpx.Response(429, request=req).raise_for_status()
    redacted = redact_exc(caught.value)
    assert "SERPAPI-SECRET-abc123" not in redacted
    assert "REDACTED" in redacted
    # The host must survive redaction so the error stays diagnosable. Parse it out
    # and compare exactly: `"serpapi.com" in redacted` would also be satisfied by
    # a host such as serpapi.com.evil.test, which is the shape of the real bug this
    # assertion would otherwise model.
    hosts = {urlparse(u).hostname for u in re.findall(r"https?://[^\s'\"]+", redacted)}
    assert any(h == "serpapi.com" for h in hosts)


def test_redact_url_covers_pii_params():
    assert "me@example.com" not in redact_url(
        "https://api.unpaywall.org/v2/10.1/x?email=me@example.com"
    )
    assert "me@example.com" not in redact_url(
        "https://api.openalex.org/works?mailto=me@example.com&per-page=50"
    )


def test_redact_url_keeps_harmless_params():
    url = "https://api.example.com/x?q=keep+this&page=2"
    assert redact_url(url) == url


def test_redact_text_handles_multiple_urls_and_no_url():
    text = "first https://a.example/x?token=AAA then https://b.example/y?api_key=BBB"
    out = redact_text(text)
    assert "AAA" not in out and "BBB" not in out
    assert redact_text("no urls here") == "no urls here"
    assert redact_text("") == ""
