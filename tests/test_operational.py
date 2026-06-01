"""Layer 5: operational + reproducibility tests.

These tests are about the system's behavior over time and across runs, not
correctness of a single function. They protect against:
- Non-determinism: two runs of the same input producing different output
- Schema drift: a code change silently breaks the JSON contract a downstream
  consumer relies on
- Audit-log shape changes: a forensic record format changes and breaks
  external log analysis

These tests are deliberately conservative — they assert what the system
must guarantee, not what would be nice to have.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ai_risk_retrieval.config import OutputConfig
from ai_risk_retrieval.models import (
    LLMJudgement,
    Paper,
    RetrievalRun,
    ScoredPaper,
    SubcategoryResult,
)
from ai_risk_retrieval.pipeline.dedup import deduplicate
from ai_risk_retrieval.pipeline.diversify import mmr_select
from ai_risk_retrieval.pipeline.rank import compute_composite_scores
from ai_risk_retrieval.storage.writer import write_run


def _make_paper(i: int) -> Paper:
    return Paper(
        title=f"Paper {i}: study of X",
        abstract="A" * 300,
        authors=[f"Author{i}"],
        year=2024,
        url=f"https://example.com/p{i}",
        source="arxiv",
        citation_count=5 + i,
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        content_hash=f"{i:064x}",
    )


def _make_scored(i: int, score: float = 7.0) -> ScoredPaper:
    return ScoredPaper(
        paper=_make_paper(i),
        llm=LLMJudgement(relevance=score, rationale=f"Rationale {i}"),
        composite_score=score,
    )


# ── Determinism ──────────────────────────────────────────────────────────────


def test_dedup_is_deterministic():
    """Same input → same output, regardless of how many times called."""
    papers = [_make_paper(i) for i in range(5)] + [_make_paper(2)]  # one dup
    r1 = deduplicate(papers, fuzzy_threshold=85)
    r2 = deduplicate(papers, fuzzy_threshold=85)
    r3 = deduplicate(papers, fuzzy_threshold=85)
    assert [p.title for p in r1] == [p.title for p in r2] == [p.title for p in r3]


def test_mmr_is_deterministic():
    """MMR selection on identical input produces identical ranking."""
    scored = [_make_scored(i, score=7.0 + i * 0.1) for i in range(10)]
    r1 = mmr_select(scored, target=5, lam=0.6)
    r2 = mmr_select(scored, target=5, lam=0.6)
    assert [s.paper.title for s in r1] == [s.paper.title for s in r2]


def test_write_run_byte_identical_for_identical_input(tmp_path: Path):
    """The output JSON for a given RetrievalRun must be byte-identical across
    writes. Downstream consumers may use content-hashing for change detection;
    spurious changes break their caching.
    """
    paper = _make_paper(1)
    judgement = LLMJudgement(relevance=8.0, rationale="Good match.")
    scored = ScoredPaper(paper=paper, llm=judgement, composite_score=7.5)
    result = SubcategoryResult(
        category_id="technical",
        category_name="Technical Risks",
        subcategory_name="Hallucinations",
        selected_papers=[scored],
        candidate_count=10,
        shortlist_count=5,
        generated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    run = RetrievalRun(
        run_id="determinism-test",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        finished_at=datetime(2024, 1, 1, 1, tzinfo=UTC),
        taxonomy_version="2.2",
        llm_model="test-model",
        results=[result],
    )

    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    cfg_a = OutputConfig(directory=str(out_a), atomic_writes=False)
    cfg_b = OutputConfig(directory=str(out_b), atomic_writes=False)
    p_a = write_run(run, cfg_a)
    p_b = write_run(run, cfg_b)
    assert p_a.read_bytes() == p_b.read_bytes()


# ── Schema stability ─────────────────────────────────────────────────────────

EXPECTED_RUN_SCHEMA_KEYS = {
    "schema_version",
    "run_id",
    "started_at",
    "finished_at",
    "taxonomy_version",
    "llm_model",
    "results",
}

EXPECTED_RESULT_KEYS = {
    "category_id",
    "category_name",
    "subcategory_name",
    "selected_papers",
    "candidate_count",
    "shortlist_count",
    "generated_at",
}

EXPECTED_SCORED_PAPER_KEYS = {
    "paper",
    "llm",
    "composite_score",
    "score_components",
}


def test_run_output_has_expected_top_level_schema(tmp_path: Path):
    """The emitted JSON must contain exactly the documented top-level keys.

    Catches accidental field renames that would silently break webapp consumers.
    """
    paper = _make_paper(1)
    judgement = LLMJudgement(relevance=8.0, rationale="ok")
    scored = ScoredPaper(paper=paper, llm=judgement, composite_score=7.5)
    result = SubcategoryResult(
        category_id="technical",
        category_name="Technical Risks",
        subcategory_name="Hallucinations",
        selected_papers=[scored],
        candidate_count=10,
        shortlist_count=5,
        generated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    run = RetrievalRun(
        run_id="schema-test",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        finished_at=datetime(2024, 1, 1, 1, tzinfo=UTC),
        taxonomy_version="2.2",
        llm_model="test-model",
        results=[result],
    )
    cfg = OutputConfig(directory=str(tmp_path), atomic_writes=False)
    p = write_run(run, cfg)
    data = json.loads(p.read_text())
    assert set(data.keys()) == EXPECTED_RUN_SCHEMA_KEYS, (
        f"Top-level schema drifted. Expected {EXPECTED_RUN_SCHEMA_KEYS}, got {set(data.keys())}"
    )


def test_run_output_results_have_expected_schema(tmp_path: Path):
    paper = _make_paper(1)
    judgement = LLMJudgement(relevance=8.0, rationale="ok")
    scored = ScoredPaper(paper=paper, llm=judgement, composite_score=7.5)
    result = SubcategoryResult(
        category_id="technical",
        category_name="Technical Risks",
        subcategory_name="Hallucinations",
        selected_papers=[scored],
        candidate_count=10,
        shortlist_count=5,
        generated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    run = RetrievalRun(
        run_id="schema-test",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        finished_at=datetime(2024, 1, 1, 1, tzinfo=UTC),
        taxonomy_version="2.2",
        llm_model="test-model",
        results=[result],
    )
    cfg = OutputConfig(directory=str(tmp_path), atomic_writes=False)
    p = write_run(run, cfg)
    data = json.loads(p.read_text())
    result_data = data["results"][0]
    assert set(result_data.keys()) == EXPECTED_RESULT_KEYS, (
        f"SubcategoryResult schema drifted. Expected {EXPECTED_RESULT_KEYS}, "
        f"got {set(result_data.keys())}"
    )


def test_run_output_scored_papers_have_expected_schema(tmp_path: Path):
    paper = _make_paper(1)
    judgement = LLMJudgement(relevance=8.0, rationale="ok")
    scored = ScoredPaper(paper=paper, llm=judgement, composite_score=7.5)
    result = SubcategoryResult(
        category_id="technical",
        category_name="Technical Risks",
        subcategory_name="Hallucinations",
        selected_papers=[scored],
        candidate_count=10,
        shortlist_count=5,
        generated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    run = RetrievalRun(
        run_id="schema-test",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        finished_at=datetime(2024, 1, 1, 1, tzinfo=UTC),
        taxonomy_version="2.2",
        llm_model="test-model",
        results=[result],
    )
    cfg = OutputConfig(directory=str(tmp_path), atomic_writes=False)
    p = write_run(run, cfg)
    data = json.loads(p.read_text())
    sp_data = data["results"][0]["selected_papers"][0]
    assert set(sp_data.keys()) == EXPECTED_SCORED_PAPER_KEYS, (
        f"ScoredPaper schema drifted. Expected {EXPECTED_SCORED_PAPER_KEYS}, "
        f"got {set(sp_data.keys())}"
    )


def test_schema_version_is_documented():
    """The schema_version field on RetrievalRun must have a value, so consumers
    can detect breaking changes by version-comparing."""
    run = RetrievalRun(
        run_id="v-test",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        finished_at=datetime(2024, 1, 1, 1, tzinfo=UTC),
        taxonomy_version="2.2",
        llm_model="test",
        results=[],
    )
    assert run.schema_version, "schema_version is empty — consumers can't detect upgrades"
    # Must be a semver-ish string
    parts = run.schema_version.split(".")
    assert len(parts) >= 2, f"schema_version {run.schema_version!r} not in MAJOR.MINOR format"


# ── Composite score reproducibility ─────────────────────────────────────────


def test_composite_score_is_deterministic():
    """compute_composite_scores on the same input produces the same scores
    in the same order. Critical for cache invalidation logic."""
    from ai_risk_retrieval.config import ScoringConfig, ScoringWeights

    judged = [
        (_make_paper(i), LLMJudgement(relevance=7.0 + i * 0.1, rationale=f"r{i}")) for i in range(5)
    ]
    config = ScoringConfig(
        weights=ScoringWeights(
            llm_relevance=0.5,
            citations=0.3,
            recency=0.15,
            source_diversity_bonus=0.05,
        ),
        min_acceptable_score=0.0,
        diversity_lambda=0.6,
    )
    r1 = compute_composite_scores(judged, config)
    r2 = compute_composite_scores(judged, config)
    r3 = compute_composite_scores(judged, config)
    assert (
        [sp.composite_score for sp in r1]
        == [sp.composite_score for sp in r2]
        == [sp.composite_score for sp in r3]
    )
    assert [sp.paper.title for sp in r1] == [sp.paper.title for sp in r2]
