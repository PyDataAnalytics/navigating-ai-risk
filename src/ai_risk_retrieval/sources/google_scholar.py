"""
Google Scholar source.

Google Scholar has NO official API. Scraping it violates Google's ToS and
results in CAPTCHAs and IP blocks. SerpAPI is the standard licensed gateway
that proxies Scholar results legally.

This source is auto-disabled if SERPAPI_API_KEY is not set. That is the
intended behavior — fail closed rather than fall back to scraping.
"""

from __future__ import annotations

from typing import Any

import structlog

from ..models import Paper, Subcategory
from .base import PaperSource, retryable, safe_text

log = structlog.get_logger()


class GoogleScholarSource(PaperSource):
    name = "google_scholar"
    base_url = "https://serpapi.com/search"

    # Tripped (process-wide, for the rest of a run) the first time SerpApi
    # reports it is out of searches. Once set, every later subcategory skips
    # the API entirely and the free sources (OpenAlex, Semantic Scholar, arXiv,
    # Papers with Code, SSRN) carry the remainder of the run. Fresh per process.
    _quota_exhausted: bool = False

    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        if not self.config.enabled or self.config.max_candidates_per_subcategory == 0:
            return []

        api_key = self.config.resolve_api_key()
        if not api_key:
            log.info(
                "google_scholar_disabled",
                reason="No SERPAPI_API_KEY in environment. "
                "Scraping Scholar directly violates ToS; this source is fail-closed.",
            )
            return []

        # SerpApi quota already spent earlier in this run → don't call the API;
        # the free sources cover the remaining subcategories.
        if GoogleScholarSource._quota_exhausted:
            return []

        query = self.build_query(subcategory)
        params = {
            "engine": "google_scholar",
            "q": query,
            "num": min(self.config.max_candidates_per_subcategory, 20),
            "api_key": api_key,
        }

        try:
            data = await self._get(params)
        except Exception as e:
            # HTTP 429 from SerpApi == out of searches / rate limit. Trip the
            # run-wide flag so we stop hammering a spent quota and fall back to
            # the free sources for every remaining subcategory.
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429:
                GoogleScholarSource._quota_exhausted = True
                log.warning(
                    "scholar_quota_exhausted",
                    detail="SerpApi returned 429; disabling Scholar for the rest of "
                    "this run and falling back to the free sources.",
                )
            else:
                log.warning("scholar_fetch_failed", subcategory=subcategory.name, error=str(e))
            return []

        # SerpApi also reports a spent quota in the JSON body (HTTP 200 with an
        # `error` string), not only via 429 — catch both.
        err = data.get("error")
        if err:
            low = err.lower()
            if any(k in low for k in ("run out", "ran out", "exceed", "quota", "limit", "no searches")):
                GoogleScholarSource._quota_exhausted = True
                log.warning(
                    "scholar_quota_exhausted",
                    error=err,
                    detail="disabling Scholar for the rest of this run; free sources continue.",
                )
            else:
                log.warning("scholar_api_error", error=err)
            return []

        papers: list[Paper] = []
        for entry in data.get("organic_results", []) or []:
            try:
                paper = self._entry_to_paper(entry)
                if paper:
                    papers.append(paper)
            except Exception as e:
                log.debug("scholar_parse_failed", error=str(e))
        return papers

    @retryable
    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        async with self.http_client() as client:
            r = await client.get(self.base_url, params=params)
            r.raise_for_status()
            return r.json()

    def _entry_to_paper(self, e: dict[str, Any]) -> Paper | None:
        title = safe_text(e.get("title", ""), 500).strip()
        if not title:
            return None
        url = e.get("link")
        if not url:
            return None

        abstract = safe_text(e.get("snippet", "") or "", 10_000).strip()
        # publication_info.summary is like "X Smith, Y Jones - Journal, 2023 - publisher.com"
        pub_info = (e.get("publication_info") or {}).get("summary", "")
        year: int | None = None
        if pub_info:
            import re
            m = re.search(r"\b(19|20)\d{2}\b", pub_info)
            if m:
                year = int(m.group(0))

        # Authors from inline_links if present, else parse from summary
        authors: list[str] = []
        inline_authors = (e.get("publication_info") or {}).get("authors") or []
        for a in inline_authors:
            if isinstance(a, dict):
                authors.append(safe_text(a.get("name", ""), 200))
        authors = authors[:200]

        cited_by = ((e.get("inline_links") or {}).get("cited_by") or {}).get("total")
        citation_count = cited_by if isinstance(cited_by, int) and cited_by >= 0 else None

        # PDF if Scholar surfaced one
        pdf_url = None
        for r in e.get("resources", []) or []:
            if r.get("file_format") == "PDF" and r.get("link"):
                pdf_url = r["link"]
                break

        return Paper(
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            venue=safe_text(pub_info, 300) or None,
            citation_count=citation_count,
            doi=None,
            arxiv_id=None,
            semantic_scholar_id=None,
            url=url,
            pdf_url=pdf_url,
            source=self.name,
            fetched_at=self.now(),
            content_hash=self.content_hash(url, title, abstract),
        )
