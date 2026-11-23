"""
arXiv source. Uses the public Atom API at http://export.arxiv.org/api/query.

API docs: https://info.arxiv.org/help/api/index.html
"""

from __future__ import annotations

from urllib.parse import quote_plus

import feedparser
import structlog

from ..models import Paper, Subcategory
from .base import PaperSource, retryable, safe_text

log = structlog.get_logger()


class ArxivSource(PaperSource):
    name = "arxiv"
    base_url = "http://export.arxiv.org/api/query"

    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        if not self.config.enabled or self.config.max_candidates_per_subcategory == 0:
            return []

        query = self._build_arxiv_query(subcategory)
        url = (
            f"{self.base_url}?search_query={quote_plus(query)}"
            f"&start=0&max_results={self.config.max_candidates_per_subcategory}"
            f"&sortBy=relevance&sortOrder=descending"
        )

        try:
            xml = await self._get(url)
        except Exception as e:
            log.warning("arxiv_fetch_failed", subcategory=subcategory.name, error=str(e))
            return []

        feed = feedparser.parse(xml)
        papers: list[Paper] = []
        for entry in feed.entries:
            try:
                paper = self._entry_to_paper(entry)
                if paper:
                    papers.append(paper)
            except Exception as e:
                # One bad entry never kills the batch
                log.debug("arxiv_parse_failed", error=str(e), entry_id=getattr(entry, "id", "?"))
        return papers

    # ── internals ───────────────────────────────────────────────────────────

    def _build_arxiv_query(self, subcategory: Subcategory) -> str:
        """
        arXiv query syntax: `ti:term AND abs:term AND cat:cs.AI`.

        We construct an OR over all keyword terms across title+abstract,
        ANDed with the category filter.
        """
        terms = [subcategory.name, *subcategory.keywords]
        # Build (ti:"x" OR abs:"x") for each term, OR'd together
        clauses = []
        for t in terms:
            quoted = f'"{t}"'
            clauses.append(f"(ti:{quoted} OR abs:{quoted})")
        term_query = " OR ".join(clauses)

        cats = self.config.arxiv_categories or []
        if cats:
            cat_query = " OR ".join(f"cat:{c}" for c in cats)
            return f"({term_query}) AND ({cat_query})"
        return term_query

    @retryable
    async def _get(self, url: str) -> str:
        async with self.http_client() as client:
            r = await client.get(url, headers={"Accept": "application/atom+xml"})
            r.raise_for_status()
            return r.text

    def _entry_to_paper(self, entry: feedparser.FeedParserDict) -> Paper | None:
        # entry.id is like http://arxiv.org/abs/2310.12345v1
        raw_id = entry.get("id", "")
        arxiv_id = raw_id.rsplit("/", 1)[-1] if raw_id else None
        if not arxiv_id:
            return None

        title = safe_text(entry.get("title", ""), 500).strip().replace("\n", " ")
        if not title:
            return None
        abstract = safe_text(entry.get("summary", ""), 10_000).strip().replace("\n", " ")
        authors = [safe_text(a.get("name", ""), 200) for a in entry.get("authors", [])][:200]

        published = entry.get("published", "")
        year: int | None = None
        if published and len(published) >= 4 and published[:4].isdigit():
            year = int(published[:4])

        # Find the PDF link if present
        pdf_url = None
        for link in entry.get("links", []):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href")
                break

        abs_url = raw_id or f"https://arxiv.org/abs/{arxiv_id}"

        return Paper(
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            publication_date=published or None,
            venue="arXiv",
            citation_count=None,  # arXiv API doesn't expose this
            doi=None,
            arxiv_id=arxiv_id,
            semantic_scholar_id=None,
            url=abs_url,
            pdf_url=pdf_url,
            source=self.name,
            fetched_at=self.now(),
            content_hash=self.content_hash(arxiv_id, title, abstract),
        )
