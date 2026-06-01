"""
OpenAlex source.

OpenAlex (https://openalex.org) is a free, open metadata graph covering
~250M scholarly works. No API key required. Coverage often exceeds the
combined Semantic Scholar + arXiv pull, especially for:
- Recent preprints from non-arXiv venues (SSRN, OSF, bioRxiv, institutional)
- Workshop and conference papers not yet indexed by S2
- Industry lab technical reports

Polite pool: passing `mailto=<email>` raises the rate limit considerably.
Set OPENALEX_MAILTO in the environment for production runs.

OpenAlex stores abstracts in an inverted-index format (`abstract_inverted_index`:
`{word: [positions]}`). We reconstruct plain text for the LLM judge.

API docs: https://docs.openalex.org/
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from ..models import Paper, Subcategory
from .base import PaperSource, retryable, safe_text

log = structlog.get_logger()


class OpenAlexSource(PaperSource):
    name = "openalex"
    base_url = "https://api.openalex.org/works"

    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        if not self.config.enabled or self.config.max_candidates_per_subcategory == 0:
            return []

        query = self.build_query(subcategory)
        # OpenAlex `search` does full-text-ish search across title + abstract.
        # `per-page` caps at 200.
        params: dict[str, Any] = {
            "search": query,
            "per-page": min(self.config.max_candidates_per_subcategory, 200),
            "sort": "relevance_score:desc",
            # Light filter: only journal articles and preprints, exclude
            # datasets / editorials / retracted. Adjust if you want broader.
            "filter": "type:article|preprint,is_retracted:false",
            # `select` keeps the response small. Listed fields are exactly
            # what we map to our Paper model below.
            "select": (
                "id,doi,title,abstract_inverted_index,authorships,publication_year,"
                "publication_date,primary_location,cited_by_count,open_access,ids,type"
            ),
        }
        # Polite pool — raises rate limit. Strongly recommended in production.
        if mailto := os.environ.get("OPENALEX_MAILTO"):
            params["mailto"] = mailto

        try:
            data = await self._get(params)
        except Exception as e:
            log.warning("openalex_fetch_failed", subcategory=subcategory.name, error=str(e))
            return []

        papers: list[Paper] = []
        for entry in data.get("results", []) or []:
            try:
                paper = self._entry_to_paper(entry)
                if paper:
                    papers.append(paper)
            except Exception as e:
                log.debug("openalex_parse_failed", error=str(e))
        return papers

    @retryable
    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        async with self.http_client() as client:
            r = await client.get(self.base_url, params=params)
            r.raise_for_status()
            return r.json()

    def _entry_to_paper(self, e: dict[str, Any]) -> Paper | None:
        title = safe_text(e.get("title", "") or "", 500).strip()
        if not title:
            return None

        abstract = self._reconstruct_abstract(e.get("abstract_inverted_index"))
        abstract = safe_text(abstract, 10_000).strip()

        # Authors come from `authorships`, each with an `author.display_name`
        authors = []
        for a in (e.get("authorships") or [])[:200]:
            name = ((a or {}).get("author") or {}).get("display_name")
            if name:
                authors.append(safe_text(name, 200))

        year = e.get("publication_year") if isinstance(e.get("publication_year"), int) else None

        # DOI: comes as full URL like "https://doi.org/10.xxx/...". Strip prefix.
        doi_raw = e.get("doi")
        doi: str | None = None
        if isinstance(doi_raw, str) and doi_raw.startswith("https://doi.org/"):
            doi = doi_raw[len("https://doi.org/") :]
        elif isinstance(doi_raw, str) and doi_raw.startswith("10."):
            doi = doi_raw

        # arXiv ID, if present, lives in ids.* or in primary_location
        ids = e.get("ids") or {}
        arxiv_id = self._extract_arxiv_id(ids.get("openalex"), e.get("primary_location"))

        # Landing page URL
        primary_loc = e.get("primary_location") or {}
        url = primary_loc.get("landing_page_url") or e.get("id")
        if not url:
            return None

        # PDF URL — OpenAlex tracks open access PDF separately
        oa = e.get("open_access") or {}
        pdf_url = oa.get("oa_url") if oa.get("is_oa") else None
        # Some entries also surface a PDF on primary_location
        if not pdf_url:
            pdf_url = primary_loc.get("pdf_url")

        # Venue — `primary_location.source.display_name`
        venue: str | None = None
        if src := (primary_loc.get("source") or {}):
            venue = safe_text(src.get("display_name", "") or "", 300) or None

        citation_count = e.get("cited_by_count")
        if not isinstance(citation_count, int) or citation_count < 0:
            citation_count = None

        # Build Paper. DOI/arxiv_id validators may reject malformed values;
        # fall back to dropping just those fields rather than the whole paper.
        try:
            return Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                publication_date=e.get("publication_date"),
                venue=venue,
                citation_count=citation_count,
                doi=doi,
                arxiv_id=arxiv_id,
                semantic_scholar_id=None,
                url=url,
                pdf_url=pdf_url,
                source=self.name,
                fetched_at=self.now(),
                content_hash=self.content_hash(url, title, abstract),
            )
        except Exception:
            return Paper(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                publication_date=e.get("publication_date"),
                venue=venue,
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

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
        """
        OpenAlex stores abstracts as {word: [positions, ...]}. We invert it
        back to a flat string. Robust against missing positions and empty input.
        """
        if not inverted or not isinstance(inverted, dict):
            return ""
        # Find max position to size the output list
        max_pos = -1
        for positions in inverted.values():
            if isinstance(positions, list) and positions:
                local_max = max(p for p in positions if isinstance(p, int))
                if local_max > max_pos:
                    max_pos = local_max
        if max_pos < 0:
            return ""
        words: list[str] = [""] * (max_pos + 1)
        for word, positions in inverted.items():
            if not isinstance(word, str) or not isinstance(positions, list):
                continue
            for p in positions:
                if isinstance(p, int) and 0 <= p <= max_pos:
                    words[p] = word
        return " ".join(w for w in words if w)

    @staticmethod
    def _extract_arxiv_id(openalex_id: str | None, primary_location: Any) -> str | None:
        """
        OpenAlex sometimes flags arXiv preprints via the primary location's
        source. We try a best-effort extraction; failure just means we lose
        the arXiv link for dedup, which is fine (DOI or title still matches).
        """
        if not isinstance(primary_location, dict):
            return None
        src = primary_location.get("source") or {}
        if not isinstance(src, dict):
            return None
        # arXiv's OpenAlex source ID is stable
        if src.get("display_name", "").lower() == "arxiv":
            # Try to pull from landing_page_url which looks like
            # https://arxiv.org/abs/2310.12345
            url = primary_location.get("landing_page_url", "") or ""
            if "arxiv.org/abs/" in url:
                tail = url.rsplit("/abs/", 1)[-1].strip()
                # Strip any trailing path/query
                tail = tail.split("?")[0].split("#")[0].rstrip("/")
                if tail:
                    return tail
        return None
