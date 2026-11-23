"""Unpaywall enrichment: fill `oa_pdf_url` for papers that have a DOI.

Entirely gated on the UNPAYWALL_EMAIL environment variable:
  - UNPAYWALL_EMAIL set   → look up each DOI's best open-access location and
                            populate Paper.oa_pdf_url.
  - UNPAYWALL_EMAIL unset → no calls, no-op, oa_pdf_url stays None.

So the retriever runs identically with or without Unpaywall configured; turning
it on is purely an environment change on the pod. The step is best-effort: a
network error, non-200, or parse failure for one paper is swallowed and simply
leaves that paper's oa_pdf_url as None — it never aborts the run.

Unpaywall API (https://unpaywall.org/products/api):
  GET https://api.unpaywall.org/v2/{doi}?email={email}
  Free, no key. The email is an identifier (and a courtesy contact). The
  suggested ceiling is ~100k calls/day, far above our ~3 papers x 218
  subcategories per run.

Scope note: we enrich only the *selected* papers (the top-N per subcategory),
not every candidate — a few hundred lookups per full run, not tens of thousands.

Legal note (mirrors the project's CC0/Option-C stance): fetching the OA URL is
metadata; storing/serving the link is fine. Do NOT fetch-and-republish the full
text — link to the OA copy instead.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable

import httpx
import structlog

log = structlog.get_logger()

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
USER_AGENT = "ai-risk-retrieval/0.1 (research; OA link enrichment)"


def unpaywall_email() -> str | None:
    """Return the configured Unpaywall email, or None if not set."""
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    return email or None


def _best_oa_pdf(payload: dict) -> str | None:
    """Extract the best open-access PDF (or landing) URL from an Unpaywall response."""
    if not isinstance(payload, dict):
        return None
    loc = payload.get("best_oa_location") or {}
    if not isinstance(loc, dict):
        return None
    url = loc.get("url_for_pdf") or loc.get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    return None


async def _lookup_one(client: httpx.AsyncClient, doi: str, email: str) -> str | None:
    try:
        r = await client.get(f"{UNPAYWALL_BASE}/{doi}", params={"email": email})
        if r.status_code != 200:
            return None
        return _best_oa_pdf(r.json())
    except Exception as e:  # network, JSON, anything — best-effort
        log.debug("unpaywall_lookup_failed", doi=doi, error=str(e))
        return None


async def enrich_papers(
    papers: Iterable,
    email: str | None = None,
    *,
    concurrency: int = 8,
    timeout_seconds: int = 20,
) -> int:
    """Populate `oa_pdf_url` on papers that have a DOI but no OA link yet.

    Mutates Paper objects in place. Returns the number of OA links added.
    No-op (returns 0) when no email is configured or no eligible papers.
    """
    email = email or unpaywall_email()
    if not email:
        return 0

    targets = [p for p in papers if getattr(p, "doi", None) and not getattr(p, "oa_pdf_url", None)]
    if not targets:
        return 0

    sem = asyncio.Semaphore(concurrency)
    filled = 0

    async with httpx.AsyncClient(
        timeout=timeout_seconds,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    ) as client:

        async def _do(paper) -> None:
            nonlocal filled
            async with sem:
                url = await _lookup_one(client, paper.doi, email)
            if url:
                try:
                    paper.oa_pdf_url = url
                    filled += 1
                except Exception as e:
                    # Assignment shouldn't fail (field is str|None), but stay safe.
                    log.debug("unpaywall_assign_failed", error=str(e))

        await asyncio.gather(*[_do(p) for p in targets], return_exceptions=True)

    return filled
