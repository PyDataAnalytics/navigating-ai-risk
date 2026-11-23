"""
SSRN source.

SSRN does not provide a public search API. Scraping SSRN directly violates
their ToS and risks IP blocking. The pragmatic, compliant approach is to use
Semantic Scholar with a `venue:SSRN` filter — S2 indexes SSRN papers and
exposes them through its supported API.

If you have legitimate SSRN API access (institutional licensing), implement
a separate adapter that uses your authorized endpoint.
"""

from __future__ import annotations

from typing import Any

import structlog

from ..models import Paper, Subcategory
from .base import PaperSource, retryable, safe_text

log = structlog.get_logger()


class SSRNSource(PaperSource):
    name = "ssrn"
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    FIELDS = "title,abstract,authors,year,publicationDate,venue,citationCount,externalIds,url,openAccessPdf"

    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        if not self.config.enabled or self.config.max_candidates_per_subcategory == 0:
            return []

        # Add venue constraint to surface SSRN-indexed items
        query = self.build_query(subcategory) + " venue:SSRN"
        params = {
            "query": query,
            "limit": min(self.config.max_candidates_per_subcategory, 100),
            "fields": self.FIELDS,
        }
        headers = {}
        # Reuse Semantic Scholar API key if set; SSRN access goes through S2.
        import os

        if api_key := os.environ.get("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = api_key

        try:
            data = await self._get(params, headers)
        except Exception as e:
            log.warning("ssrn_fetch_failed", subcategory=subcategory.name, error=str(e))
            return []

        papers: list[Paper] = []
        for entry in data.get("data", []) or []:
            try:
                paper = self._entry_to_paper(entry)
                if paper:
                    papers.append(paper)
            except Exception as e:
                log.debug("ssrn_parse_failed", error=str(e))
        return papers

    @retryable
    async def _get(self, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        async with self.http_client() as client:
            r = await client.get(self.base_url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()

    def _entry_to_paper(self, e: dict[str, Any]) -> Paper | None:
        title = safe_text(e.get("title", ""), 500).strip()
        if not title:
            return None
        venue = safe_text(e.get("venue", "") or "", 300)
        # Belt-and-braces: only keep if venue actually contains SSRN
        if "ssrn" not in venue.lower():
            return None

        abstract = safe_text(e.get("abstract", "") or "", 10_000).strip()
        authors = [safe_text(a.get("name", ""), 200) for a in (e.get("authors") or [])][:200]
        year = e.get("year") if isinstance(e.get("year"), int) else None

        ext_ids = e.get("externalIds") or {}
        doi = ext_ids.get("DOI")
        s2_id = e.get("paperId")
        url = e.get("url") or (f"https://www.semanticscholar.org/paper/{s2_id}" if s2_id else None)
        if not url:
            return None
        pdf_url = (
            (e.get("openAccessPdf") or {}).get("url")
            if isinstance(e.get("openAccessPdf"), dict)
            else None
        )

        citation_count = e.get("citationCount")
        if not isinstance(citation_count, int) or citation_count < 0:
            citation_count = None

        try:
            return Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                publication_date=e.get("publicationDate"),
                venue=venue or "SSRN",
                citation_count=citation_count,
                doi=doi,
                arxiv_id=None,
                semantic_scholar_id=s2_id,
                url=url,
                pdf_url=pdf_url,
                source=self.name,
                fetched_at=self.now(),
                content_hash=self.content_hash(s2_id or url, title, abstract),
            )
        except Exception:
            return Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                publication_date=e.get("publicationDate"),
                venue=venue or "SSRN",
                citation_count=citation_count,
                doi=None,
                arxiv_id=None,
                semantic_scholar_id=s2_id,
                url=url,
                pdf_url=pdf_url,
                source=self.name,
                fetched_at=self.now(),
                content_hash=self.content_hash(s2_id or url, title, abstract),
            )
