"""Smoke tests for the Layer 2 benchmark harness.

These tests do NOT gate on matcher quality — they just verify the harness
itself works end-to-end and the golden set is well-formed. Quality gates
on matcher recall come later, once we have a baseline number we want to
guard against regression.
"""

from __future__ import annotations

from pathlib import Path

from ai_risk_retrieval.benchmark import (
    KeywordOverlapMatcher,
    load_golden_set,
    run_benchmark,
)

REPO = Path(__file__).resolve().parent.parent
GOLDEN_SET = REPO / "tests" / "golden_set" / "queries.yaml"


def test_golden_set_loads_without_drift():
    """Golden set must parse and every `expected` must be a canonical name."""
    queries = load_golden_set()
    assert len(queries) > 0, "Golden set is empty"
    for q in queries:
        assert "query" in q
        assert "expected" in q
        assert isinstance(q["expected"], list)
        assert len(q["expected"]) > 0
        assert "difficulty" in q
        assert q["difficulty"] in {"easy", "medium", "hard"}


def test_golden_set_has_difficulty_coverage():
    """Need at least 5 queries per difficulty class to make per-class metrics
    meaningful."""
    queries = load_golden_set()
    counts: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    for q in queries:
        counts[q["difficulty"]] = counts.get(q["difficulty"], 0) + 1
    for diff, n in counts.items():
        assert n >= 5, f"Difficulty '{diff}' has only {n} queries (need ≥5)"


def test_baseline_matcher_runs():
    """The keyword-overlap baseline must run without errors."""
    matcher = KeywordOverlapMatcher.from_definitions()
    report = run_benchmark(matcher)
    assert len(report.results) > 0


def test_baseline_matcher_meets_floor():
    """The keyword baseline must achieve at least R@10 ≥ 0.70 overall.

    This is a sanity floor: if even the simple baseline can't find the
    right answer in top-10 most of the time, either the taxonomy is broken
    or the golden set is wrong. Either way we want to know.

    Note: this guards against *regression*. If the baseline drops below
    this number after a change, something is wrong with the data or the
    harness.
    """
    matcher = KeywordOverlapMatcher.from_definitions()
    report = run_benchmark(matcher)
    r10 = report.recall_at(10)
    assert r10 >= 0.70, (
        f"Baseline R@10 dropped to {r10:.2f} (floor 0.70). Report:\n{report.summary()}"
    )


def test_baseline_easy_queries_perfect():
    """Easy queries (those using subcategory-name words) must hit R@1=1.0
    on the baseline. If they don't, the keyword tokenizer or stop-word
    list is broken.
    """
    matcher = KeywordOverlapMatcher.from_definitions()
    report = run_benchmark(matcher)
    r1_easy = report.recall_at(1, difficulty="easy")
    assert r1_easy == 1.0, (
        f"Baseline R@1 on easy queries dropped to {r1_easy:.2f} (expected 1.0). "
        f"This usually indicates a tokenizer or stop-word regression."
    )
