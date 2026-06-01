"""
Papers With Code source. Useful when implementation/benchmark linkage matters.

API: https://paperswithcode.com/api/v1/docs/
"""

from __future__ import annotations

from typing import Any

import structlog

from ..models import Paper, Subcategory
from .base import PaperSource, retryable, safe_text

log = structlog.get_logger()


class PapersWithCodeSource(PaperSource):
    name = "papers_with_code"
    base_url = "https://paperswithcode.com/api/v1/papers/"

    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        if not self.config.enabled or self.config.max_candidates_per_subcategory == 0:
            return []

        query = self.build_query(subcategory)
        params = {
            "q": query,
            "page": 1,
            "items_per_page": min(self.config.max_candidates_per_subcategory, 50),
        }

        try:
            data = await self._get(params)
        except Exception as e:
            log.warning("pwc_fetch_failed", subcategory=subcategory.name, error=str(e))
            return []

        papers: list[Paper] = []
        for entry in data.get("results", []) or []:
            try:
                paper = self._entry_to_paper(entry)
                if paper:
                    papers.append(paper)
            except Exception as e:
                log.debug("pwc_parse_failed", error=str(e))
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
        abstract = safe_text(e.get("abstract", "") or "", 10_000).strip()
        # PWC returns "authors" as a list of strings
        authors_raw = e.get("authors") or []
        if authors_raw and isinstance(authors_raw[0], dict):
            authors = [safe_text(a.get("name", ""), 200) for a in authors_raw][:200]
        else:
            authors = [safe_text(a, 200) for a in authors_raw][:200]

        year: int | None = None
        if pub := e.get("published"):
            if isinstance(pub, str) and len(pub) >= 4 and pub[:4].isdigit():
                year = int(pub[:4])

        arxiv_id = e.get("arxiv_id")
        # PWC sometimes returns an empty string; convert to None
        if isinstance(arxiv_id, str) and not arxiv_id.strip():
            arxiv_id = None

        url = e.get("url_abs") or e.get("url_pdf")
        if not url:
            return None
        pdf_url = e.get("url_pdf") or None

        try:
            return Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                publication_date=e.get("published"),
                venue=safe_text(e.get("proceeding", "") or "", 300) or "Papers With Code",
                citation_count=None,
                doi=None,
                arxiv_id=arxiv_id,
                semantic_scholar_id=None,
                url=url,
                pdf_url=pdf_url,
                source=self.name,
                fetched_at=self.now(),
                content_hash=self.content_hash(url, title, abstract),
            )
        except Exception:
            # Bad arxiv_id format — drop the field
            return Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                publication_date=e.get("published"),
                venue=safe_text(e.get("proceeding", "") or "", 300) or "Papers With Code",
                citation_count=None,
                doi=None,
                arxiv_id=None,
                semantic_scholar_id=None,
                url=url,
                pdf_url=pdf_url,
                source=self.name,
                fetched_at=self.now(),
                content_hash=self.content_hash(url, title, abstract),
            )
