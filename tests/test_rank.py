"""Tests for shortlist and composite scoring."""

from datetime import UTC, datetime

from ai_risk_retrieval.config import ScoringConfig, ScoringWeights
from ai_risk_retrieval.models import LLMJudgement, Paper
from ai_risk_retrieval.pipeline.rank import (
    compute_composite_scores,
    shortlist_for_judging,
)


def _paper(
    title: str,
    source: str = "arxiv",
    citations: int | None = None,
    year: int | None = None,
    abstract_len: int = 500,
) -> Paper:
    return Paper(
        title=title,
        abstract="x" * abstract_len,
        url=f"https://example.com/{title}",
        source=source,  # type: ignore
        fetched_at=datetime.now(UTC),
        content_hash="a" * 64,
        citation_count=citations,
        year=year,
    )


def test_shortlist_prefers_cited_recent_papers():
    papers = [
        _paper("old uncited", citations=0, year=2010),
        _paper("recent uncited", citations=0, year=2024),
        _paper("recent highly cited", citations=500, year=2024),
        _paper("old highly cited", citations=500, year=2015),
    ]
    top = shortlist_for_judging(papers, shortlist_size=2, current_year=2025)
    titles = [p.title for p in top]
    assert "recent highly cited" in titles
    # Should beat "old uncited"
    assert "old uncited" not in titles


def test_shortlist_respects_size():
    papers = [_paper(f"paper {i}") for i in range(20)]
    top = shortlist_for_judging(papers, shortlist_size=5)
    assert len(top) == 5


def test_shortlist_uses_citation_velocity_not_absolute():
    """
    The headline citation-velocity correction: a recent paper with strong
    per-year citations beats an older paper with a higher absolute total
    accumulated more slowly.
    """
    # Velocities at year=2025:
    #   old_giant:  500 / 15 ≈ 33/yr
    #   new_hot:    100 / 1  = 100/yr   ← should win on velocity
    papers = [
        _paper("old_giant", citations=500, year=2010),
        _paper("new_hot", citations=100, year=2024),
    ]
    top = shortlist_for_judging(papers, shortlist_size=1, current_year=2025)
    assert top[0].title == "new_hot"


def test_composite_uses_citation_velocity():
    """
    Same correction in the post-LLM composite score: when LLM relevance is
    tied, the higher-velocity paper wins on the citations component.
    """
    config = ScoringConfig(
        weights=ScoringWeights(
            llm_relevance=0.0,  # remove LLM signal so we see only citations + recency
            citations=0.5,
            recency=0.5,
            source_diversity_bonus=0.0,
        ),
        min_acceptable_score=0.0,
    )
    old_giant = _paper("old_giant", citations=500, year=2010)  # ~33/yr, recency 0
    new_hot = _paper("new_hot", citations=100, year=2024)  # ~100/yr, recency 9
    judged = [
        (old_giant, LLMJudgement(relevance=5.0, rationale="ok")),
        (new_hot, LLMJudgement(relevance=5.0, rationale="ok")),
    ]
    result = compute_composite_scores(judged, config, current_year=2025)
    assert result[0].paper.title == "new_hot"


def test_composite_score_weights_applied():
    config = ScoringConfig(
        weights=ScoringWeights(
            llm_relevance=1.0,
            citations=0.0,
            recency=0.0,
            source_diversity_bonus=0.0,
        ),
        min_acceptable_score=0.0,
    )
    p1 = _paper("a", citations=100, year=2025)
    p2 = _paper("b", citations=0, year=2010)
    judged = [
        (p1, LLMJudgement(relevance=2.0, rationale="meh")),
        (p2, LLMJudgement(relevance=9.0, rationale="great")),
    ]
    result = compute_composite_scores(judged, config, current_year=2025)
    # With pure LLM weight, p2 should rank higher despite worse citations/year
    assert result[0].paper.title == "b"
    assert result[0].composite_score > result[1].composite_score


def test_source_diversity_bonus():
    """When two sources are tied on LLM/citations, a bonus goes to under-represented ones."""
    config = ScoringConfig(
        weights=ScoringWeights(
            llm_relevance=0.5,
            citations=0.25,
            recency=0.20,
            source_diversity_bonus=0.05,
        ),
        min_acceptable_score=0.0,
    )
    papers = [
        _paper("a1", source="arxiv", citations=10, year=2024),
        _paper("a2", source="arxiv", citations=10, year=2024),
        _paper("s1", source="semantic_scholar", citations=10, year=2024),
    ]
    judged = [(p, LLMJudgement(relevance=8.0, rationale="ok")) for p in papers]
    result = compute_composite_scores(judged, config, current_year=2025)
    # The semantic_scholar paper should get the diversity bonus over the second arxiv
    sources_in_order = [r.paper.source for r in result]
    # At least one source switch among the top results
    assert "semantic_scholar" in sources_in_order[:2]
