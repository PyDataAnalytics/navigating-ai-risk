"""Layer 2 benchmark harness: golden-set evaluation of matchers.

The harness defines a pluggable Matcher protocol and runs it against the
golden set in tests/golden_set/queries.yaml. It produces recall@K metrics
overall and broken down by difficulty class.

Usage:
    from ai_risk_retrieval.benchmark import run_benchmark, KeywordOverlapMatcher
    matcher = KeywordOverlapMatcher.from_definitions()
    report = run_benchmark(matcher)
    print(report.summary())

This module ships with a deterministic KeywordOverlapMatcher as a no-LLM
baseline so the harness produces a meaningful number even before the
LLM-based matcher is integrated. The real matcher (in this codebase, the
two-stage LLM screen+judge) plugs into the same Protocol.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

REPO = Path(__file__).resolve().parent.parent.parent.parent
CONFIG = REPO / "config"
GOLDEN_SET = REPO / "tests" / "golden_set" / "queries.yaml"


# ---------------------------------------------------------------------------
# Matcher protocol — pluggable contract
# ---------------------------------------------------------------------------


class Matcher(Protocol):
    """A matcher takes a query string and returns a ranked list of canonical
    subcategory names (most-relevant first). The list may be shorter or
    longer than K; the harness consumes top-K from it.
    """

    def match(self, query: str) -> list[str]: ...


# ---------------------------------------------------------------------------
# Report data structures
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    query: str
    expected: list[str]
    ranked: list[str]
    difficulty: str
    rank_of_first_hit: int | None  # 1-indexed rank of first expected match; None if none in result

    def hit_at(self, k: int) -> bool:
        if self.rank_of_first_hit is None:
            return False
        return self.rank_of_first_hit <= k


@dataclass
class BenchmarkReport:
    results: list[QueryResult]
    k_values: tuple[int, ...] = (1, 3, 5, 10)

    def recall_at(self, k: int, difficulty: str | None = None) -> float:
        scope = [r for r in self.results if difficulty is None or r.difficulty == difficulty]
        if not scope:
            return 0.0
        hits = sum(1 for r in scope if r.hit_at(k))
        return hits / len(scope)

    def mean_reciprocal_rank(self, difficulty: str | None = None) -> float:
        scope = [r for r in self.results if difficulty is None or r.difficulty == difficulty]
        if not scope:
            return 0.0
        rr_sum = sum(1.0 / r.rank_of_first_hit if r.rank_of_first_hit else 0.0 for r in scope)
        return rr_sum / len(scope)

    def difficulty_counts(self) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for r in self.results:
            c[r.difficulty] += 1
        return dict(c)

    def summary(self) -> str:
        out = [f"Benchmark report: {len(self.results)} queries"]
        out.append(f"Difficulty breakdown: {self.difficulty_counts()}")
        out.append("")
        out.append(f"{'Slice':<14} | " + " | ".join(f"R@{k:<2}" for k in self.k_values) + " | MRR")
        out.append("-" * 60)

        # Overall
        row = ["overall".ljust(14)]
        for k in self.k_values:
            row.append(f"{self.recall_at(k):.2f}".ljust(4))
        row.append(f"{self.mean_reciprocal_rank():.2f}")
        out.append(" | ".join(row))

        # Per difficulty
        for difficulty in ("easy", "medium", "hard"):
            row = [difficulty.ljust(14)]
            for k in self.k_values:
                row.append(f"{self.recall_at(k, difficulty):.2f}".ljust(4))
            row.append(f"{self.mean_reciprocal_rank(difficulty):.2f}")
            out.append(" | ".join(row))

        # Failures
        misses = [r for r in self.results if not r.hit_at(self.k_values[-1])]
        if misses:
            out.append("")
            out.append(f"Queries missing from top-{self.k_values[-1]}:")
            for r in misses[:10]:
                out.append(f"  [{r.difficulty}] {r.query[:70]}")
                out.append(f"    expected: {r.expected}")
                out.append(f"    got top-3: {r.ranked[:3]}")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Baseline matcher — deterministic keyword overlap
# ---------------------------------------------------------------------------

# Tokens to drop when computing overlap. Domain-agnostic stop words.
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
    "without",
    "but",
    "if",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "any",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "ai",
    "i",
    "you",
    "we",
    "they",
    "he",
    "she",
    "do",
    "does",
    "doing",
    "done",
    "system",
    "systems",
    "use",
    "used",
    "using",
    "user",
    "users",
    "make",
    "made",
    "get",
    "got",
}

_TOKEN_RE = re.compile(r"[a-z][a-z0-9'-]+")


def _tokenize(text: str) -> set[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 2}


@dataclass
class KeywordOverlapMatcher:
    """Baseline matcher: scores subcategories by token overlap between the
    query and (subcategory_name + one_line + applies_when + user_signals).

    Deterministic, no dependencies on LLM or embeddings. The benchmark
    number this produces is a *floor* — anything more sophisticated should
    beat it.
    """

    # Per-subcategory token bags, built once at construction
    token_bags: dict[str, set[str]] = field(default_factory=dict)
    canonical_order: list[str] = field(default_factory=list)

    @classmethod
    def from_definitions(cls, defs_path: Path | None = None) -> KeywordOverlapMatcher:
        defs_path = defs_path or (CONFIG / "subcategory_definitions.yaml")
        defs = yaml.safe_load(defs_path.read_text(encoding="utf-8"))
        token_bags = {}
        order = []
        for sc in defs["subcategories"]:
            name = sc["name"]
            order.append(name)
            text = " ".join(
                [
                    name,
                    sc.get("one_line", ""),
                    " ".join(sc.get("applies_when", [])),
                    " ".join(sc.get("user_signals", [])),
                ]
            )
            token_bags[name] = _tokenize(text)
        return cls(token_bags=token_bags, canonical_order=order)

    def match(self, query: str) -> list[str]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return list(self.canonical_order)
        scored = []
        for name, bag in self.token_bags.items():
            if not bag:
                scored.append((0.0, name))
                continue
            inter = len(q_tokens & bag)
            # Jaccard-ish: intersection / sqrt(|query| * |bag|) to avoid bias
            # toward long bags.
            score = inter / ((len(q_tokens) * len(bag)) ** 0.5)
            scored.append((score, name))
        # Tiebreak: canonical-order index (stable)
        order_idx = {n: i for i, n in enumerate(self.canonical_order)}
        scored.sort(key=lambda x: (-x[0], order_idx[x[1]]))
        return [name for _, name in scored]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def load_golden_set(path: Path | None = None) -> list[dict]:
    """Load and validate the golden-set YAML.

    Validates that every `expected` entry is a canonical subcategory name.
    Raises ValueError on any unknown name — the golden set must not drift
    against the taxonomy.
    """
    path = path or GOLDEN_SET
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    queries = data["queries"]

    # Drift check
    defs = yaml.safe_load((CONFIG / "subcategory_definitions.yaml").read_text(encoding="utf-8"))
    canonical = {sc["name"] for sc in defs["subcategories"]}
    bad = []
    for q in queries:
        for exp in q["expected"]:
            if exp not in canonical:
                bad.append((q["query"][:50], exp))
    if bad:
        raise ValueError(f"Golden set references non-canonical names: {bad}")

    return queries


def run_benchmark(
    matcher: Matcher,
    queries: list[dict] | None = None,
    k_values: tuple[int, ...] = (1, 3, 5, 10),
) -> BenchmarkReport:
    """Run the matcher against the golden set, produce a report."""
    if queries is None:
        queries = load_golden_set()
    results = []
    for q in queries:
        ranked = matcher.match(q["query"])
        # Find rank of first expected hit (1-indexed)
        rank_of_first = None
        for i, name in enumerate(ranked, 1):
            if name in q["expected"]:
                rank_of_first = i
                break
        results.append(
            QueryResult(
                query=q["query"],
                expected=list(q["expected"]),
                ranked=ranked[: max(k_values)],
                difficulty=q.get("difficulty", "unknown"),
                rank_of_first_hit=rank_of_first,
            )
        )
    return BenchmarkReport(results=results, k_values=k_values)
