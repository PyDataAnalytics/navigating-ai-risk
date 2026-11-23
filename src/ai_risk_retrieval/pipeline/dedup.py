"""
Cross-source deduplication.

Multiple sources will return the same paper. We merge them, preferring the
source with richest metadata (typically Semantic Scholar for citation counts).
"""

from __future__ import annotations

import structlog
from rapidfuzz import fuzz

from ..models import Paper

log = structlog.get_logger()


# Priority order when merging: source with higher priority "wins" for fields
# like citation_count. Semantic Scholar and OpenAlex have the most reliable
# citation counts, so they rank highest. arXiv is a preprint server and sits
# last so a peer-reviewed record wins the merge when one exists — but arXiv's
# canonical PDF is not lost: _merge_group below fills pdf_url (and any other
# blank field) from lower-priority sources. Adjust if you observe one source
# giving systematically worse metadata in your domain.
#
# Listed in descending priority. Order here is documentation only: lookups go
# through _SOURCE_PRIORITY.get(), so reordering cannot change behaviour.
_SOURCE_PRIORITY = {
    "semantic_scholar": 5,
    "openalex": 4,
    "papers_with_code": 2,
    "ssrn": 2,
    "google_scholar": 1,
    "arxiv": 0,  # preprints: lowest priority on merge (kept; PDF filled below)
}


def deduplicate(papers: list[Paper], fuzzy_threshold: int = 92) -> list[Paper]:
    """
    Two-pass dedup:
    1. Exact match on dedup_key (DOI / arXiv ID / normalized title)
    2. Fuzzy title match for remaining papers (threshold from config)

    Within a duplicate group, we merge fields, preferring the higher-priority
    source's metadata, then return one Paper per group.
    """
    if not papers:
        return []

    # Phase 1: group by dedup_key
    groups: dict[str, list[Paper]] = {}
    for p in papers:
        groups.setdefault(p.dedup_key(), []).append(p)

    representatives = [_merge_group(g) for g in groups.values()]

    # Phase 2: fuzzy merge of any remaining near-duplicate titles
    final: list[Paper] = []
    for paper in representatives:
        merged = False
        for i, existing in enumerate(final):
            score = fuzz.token_set_ratio(paper.title.lower(), existing.title.lower())
            if score >= fuzzy_threshold:
                final[i] = _merge_group([existing, paper])
                merged = True
                break
        if not merged:
            final.append(paper)

    log.debug(
        "dedup_complete",
        input=len(papers),
        after_exact=len(representatives),
        after_fuzzy=len(final),
    )
    return final


def _merge_group(group: list[Paper]) -> Paper:
    """Pick the highest-priority paper and fill its empty fields from others."""
    if len(group) == 1:
        return group[0]

    # Sort by source priority (desc), then by completeness
    def quality_key(p: Paper) -> tuple[int, int]:
        priority = _SOURCE_PRIORITY.get(p.source, 0)
        completeness = sum(
            1 for v in (p.abstract, p.doi, p.arxiv_id, p.citation_count, p.year) if v
        )
        return (priority, completeness)

    sorted_group = sorted(group, key=quality_key, reverse=True)
    primary = sorted_group[0]
    # Fill blanks from secondaries
    data = primary.model_dump()
    for other in sorted_group[1:]:
        for field in (
            "abstract",
            "doi",
            "arxiv_id",
            "semantic_scholar_id",
            "year",
            "venue",
            "pdf_url",
        ):
            if not data.get(field):
                val = getattr(other, field, None)
                if val:
                    data[field] = val
        # Fill citation_count from the highest-PRIORITY secondary that has
        # one. Note this is not the largest count, and a primary already
        # reporting 0 blocks the fill (0 is not None) — intentional, since a
        # trusted source reporting 0 citations is data, not a missing value.
        if data.get("citation_count") is None and other.citation_count is not None:
            data["citation_count"] = other.citation_count
        # Union authors if primary list was empty
        if not data.get("authors") and other.authors:
            data["authors"] = other.authors

    # Re-validate by constructing a new Paper; if the merged values somehow
    # violate the schema, fall back to primary unchanged.
    try:
        return Paper.model_validate(data)
    except Exception:
        log.debug("merge_validation_failed_falling_back", title=primary.title[:60])
        return primary
