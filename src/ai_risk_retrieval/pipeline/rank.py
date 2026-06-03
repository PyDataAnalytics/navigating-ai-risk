"""
Ranking logic.

Two ranking steps:

1. `shortlist_for_judging`: cheap pre-ranking to pick the top N candidates
   to send to the LLM (the most expensive step). We can't afford to judge
   every paper from every source.

2. `compute_composite_scores`: post-LLM combination of:
     - LLM relevance score (0-10)
     - Citation velocity (citations / age in years, log-scaled)
     - Recency
     - Source diversity bonus

   Citation *velocity* (per-year), not absolute citations, is used because
   absolute counts bias heavily toward older papers — a 2015 paper with 100
   citations would otherwise beat a 2024 paper with 60. Velocity is a fairer
   signal of impact-per-unit-time.

   Weights come from config so the operator can tune to their preferences.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from ..config import ScoringConfig
from ..models import LLMJudgement, Paper, ScoredPaper

# ─── Pre-LLM shortlist ──────────────────────────────────────────────────────


def shortlist_for_judging(
    papers: list[Paper], shortlist_size: int, current_year: int | None = None
) -> list[Paper]:
    """
    Cheap heuristic ranking before the LLM step.

    We can't run the LLM on every candidate from every source; the shortlist
    picks the most plausible ones using signals available without an LLM:
    citation count, recency, and abstract length (longer abstracts are more
    likely to actually be on-topic and easier to judge).

    This is *not* the final ranking — the LLM re-evaluates these.
    """
    if not papers:
        return []
    year_now = current_year or datetime.now(timezone.utc).year

    def heuristic_score(p: Paper) -> float:
        # Citation velocity: log(citations / max(1, age_years)). This corrects
        # for the unfair advantage older papers have under absolute citation
        # counts — a 2024 paper with 30 cites/year beats a 2015 paper with
        # the same total accumulated over a decade.
        age_years = max(1, year_now - p.year) if p.year else 10
        velocity = (p.citation_count or 0) / age_years
        velocity_log = math.log1p(velocity)
        # Recency: linear decay over 10 years
        age = max(0, year_now - p.year) if p.year else 10
        recency = max(0.0, 1.0 - age / 10.0)
        # Abstract richness
        abstract_len = min(len(p.abstract or ""), 2000) / 2000.0
        return 0.5 * velocity_log + 0.3 * (recency * 5.0) + 0.2 * (abstract_len * 5.0)

    sorted_papers = sorted(papers, key=heuristic_score, reverse=True)
    return sorted_papers[:shortlist_size]


# ─── Post-LLM composite scoring ─────────────────────────────────────────────


def compute_composite_scores(
    judged: list[tuple[Paper, LLMJudgement]],
    config: ScoringConfig,
    current_year: int | None = None,
) -> list[ScoredPaper]:
    """
    Combine signals into a final score and return ScoredPaper objects sorted
    by composite_score descending.

    All component scores are normalized to [0, 10] so the weighted sum stays
    in [0, 10] (assuming weights sum to 1.0, which Pydantic enforces).
    """
    if not judged:
        return []
    year_now = current_year or datetime.now(timezone.utc).year
    w = config.weights

    # Citation velocity (per-year). We compute log(velocity+1) for each paper,
    # then normalize against the max in this batch so the component is in [0, 10].
    # This corrects for the bias toward old papers in absolute-citation ranking.
    def _velocity(p: Paper) -> float:
        if not p.citation_count:
            return 0.0
        age_years = max(1, year_now - p.year) if p.year else 10
        return p.citation_count / age_years

    velocities = [_velocity(p) for p, _ in judged]
    max_log_velocity = math.log1p(max(velocities)) if velocities and max(velocities) > 0 else 1.0

    # Source diversity bonus is applied AFTER initial sort, so we compute
    # base scores first, then award bonuses to under-represented sources.
    scored: list[ScoredPaper] = []
    for paper, judgement in judged:
        # LLM relevance: already [0, 10]
        llm_component = judgement.relevance

        # Citation velocity, log-normalized to [0, 10]
        v_log = math.log1p(_velocity(paper))
        if max_log_velocity > 0:
            cite_component = (v_log / max_log_velocity) * 10.0
        else:
            cite_component = 0.0

        # Recency: 0 if >10 years old, 10 if this year
        if paper.year is not None:
            age = max(0, year_now - paper.year)
            recency_component = max(0.0, 10.0 - age)
        else:
            recency_component = 0.0

        base = (
            w.llm_relevance * llm_component
            + w.citations * cite_component
            + w.recency * recency_component
        )

        # arXiv de-prioritization: demote papers whose canonical source is still
        # arXiv (a preprint that didn't merge into a published record during
        # dedup). Published/indexed papers are untouched; preprints are lowered,
        # not removed. getattr keeps this a no-op if arxiv_penalty isn't set.
        penalty = getattr(config, "arxiv_penalty", 0.0)
        if penalty and paper.source == "arxiv":
            base = max(0.0, base - penalty)

        components = {
            "llm_relevance": llm_component,
            "citations": cite_component,
            "recency": recency_component,
            "source_diversity_bonus": 0.0,  # filled in below
        }
        scored.append(
            ScoredPaper(
                paper=paper,
                llm=judgement,
                composite_score=round(base, 3),
                score_components=components,
            )
        )

    # Source diversity bonus: when scanning the top-K, award a small bonus
    # to a paper from a source not yet represented. This is the standard
    # MMR-style approach; it slightly demotes "all top 3 from arXiv" outcomes.
    scored.sort(key=lambda sp: sp.composite_score, reverse=True)
    seen_sources: set[str] = set()
    bonus_pool = w.source_diversity_bonus * 10.0  # max bonus per paper, in same units
    for sp in scored[: max(10, len(scored))]:
        if sp.paper.source not in seen_sources and len(seen_sources) > 0:
            sp.score_components["source_diversity_bonus"] = bonus_pool
            sp.composite_score = round(min(10.0, sp.composite_score + bonus_pool), 3)
        seen_sources.add(sp.paper.source)

    # Re-sort after bonuses
    scored.sort(key=lambda sp: sp.composite_score, reverse=True)
    return scored
