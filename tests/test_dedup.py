"""Tests for cross-source deduplication."""

from datetime import UTC, datetime

from ai_risk_retrieval.models import Paper
from ai_risk_retrieval.pipeline.dedup import deduplicate


def _make_paper(
    title: str,
    source: str,
    doi: str | None = None,
    arxiv_id: str | None = None,
    citations: int | None = None,
    abstract: str = "A reasonable abstract about something.",
) -> Paper:
    return Paper(
        title=title,
        abstract=abstract,
        url=f"https://example.com/{source}/{title.replace(' ', '_')}",
        source=source,  # type: ignore
        fetched_at=datetime.now(UTC),
        content_hash="a" * 64,
        doi=doi,
        arxiv_id=arxiv_id,
        citation_count=citations,
    )


def test_dedup_by_doi():
    p1 = _make_paper("Same Paper", "arxiv", doi="10.1234/foo", citations=None)
    p2 = _make_paper("Same Paper", "semantic_scholar", doi="10.1234/foo", citations=50)
    result = deduplicate([p1, p2])
    assert len(result) == 1
    # S2 wins on priority; should carry the citation count
    assert result[0].citation_count == 50


def test_dedup_by_arxiv_id_ignores_version():
    p1 = _make_paper("X", "arxiv", arxiv_id="2310.12345v1")
    p2 = _make_paper("X", "arxiv", arxiv_id="2310.12345v2")
    result = deduplicate([p1, p2])
    assert len(result) == 1


def test_fuzzy_title_dedup():
    p1 = _make_paper("On the dangers of stochastic parrots", "arxiv")
    p2 = _make_paper(
        "On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?",
        "google_scholar",
    )
    result = deduplicate([p1, p2], fuzzy_threshold=80)
    assert len(result) == 1


def test_different_papers_not_merged():
    p1 = _make_paper("Paper about apples", "arxiv")
    p2 = _make_paper("Paper about bicycles", "arxiv")
    result = deduplicate([p1, p2])
    assert len(result) == 2


def test_empty_input():
    assert deduplicate([]) == []
