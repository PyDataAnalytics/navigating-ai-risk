"""End-to-end pipeline runner tests.

We mock the two external dependencies (paper sources and LLM judge) so the
orchestration code in `pipeline/runner.py` is exercised against deterministic
inputs. This catches plumbing bugs that unit tests on individual modules
miss: wrong field passed between stages, off-by-one in shortlisting, missing
error handling for empty source results, etc.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_risk_retrieval.config import (
    AppConfig,
    LLMConfig,
    LLMScreenConfig,
    OutputConfig,
    RetrievalConfig,
    RuntimeConfig,
    ScoringConfig,
    SourceConfig,
    SourcesConfig,
)
from ai_risk_retrieval.models import (
    Category,
    LLMJudgement,
    Paper,
    Subcategory,
)
from ai_risk_retrieval.pipeline.runner import run_subcategory
from ai_risk_retrieval.sources.base import PaperSource

# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeSource(PaperSource):
    """Returns a pre-canned list of papers regardless of query."""

    def __init__(self, name: str, papers: list[Paper]) -> None:
        # Don't call super().__init__ because we don't need real config
        self.name = name
        self._papers = papers
        self.timeout_seconds = 30

    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        return list(self._papers)


class FailingSource(PaperSource):
    """A source that always raises — used to verify the runner handles per-source failures gracefully."""

    def __init__(self, name: str = "failing", exc: Exception | None = None) -> None:
        self.name = name
        self._exc = exc or RuntimeError("source down")
        self.timeout_seconds = 30

    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        raise self._exc


class FakeJudge:
    """Stand-in for LLMJudge that returns a deterministic score per paper.

    Score is derived from a hash of the title so different papers get
    different scores but the same paper always gets the same score.
    """

    def __init__(self, base_score: float = 7.0) -> None:
        self.base = base_score
        self.call_count = 0

    async def score(self, paper: Paper, subcategory: Subcategory) -> LLMJudgement:
        self.call_count += 1
        # Deterministic score: derived from title length
        s = self.base + (len(paper.title) % 3) * 0.5  # in [base, base+1.0]
        s = min(10.0, max(0.0, s))
        return LLMJudgement(relevance=s, rationale=f"Fake judge: matched {subcategory.name}")


# ── Fixtures ─────────────────────────────────────────────────────────────────


# Distinct topic per index. Each fixture paper is meant to be a *different*
# paper, so its title must differ by more than a trailing number — otherwise
# the (correct) fuzzy title dedup collapses them all into one. 24 topics
# comfortably covers every range(...) used below.
_TOPICS = [
    "adversarial robustness",
    "data poisoning",
    "reward hacking",
    "model collapse",
    "prompt injection",
    "membership inference",
    "gradient leakage",
    "backdoor triggers",
    "distribution shift",
    "calibration failure",
    "spurious correlation",
    "label noise",
    "catastrophic forgetting",
    "training instability",
    "reward misspecification",
    "goal drift",
    "deceptive alignment",
    "sycophancy bias",
    "jailbreak transfer",
    "watermark removal",
    "capability overhang",
    "emergent deception",
    "scalable oversight",
    "interpretability gaps",
]


def _make_paper(i: int, year: int = 2024) -> Paper:
    topic = _TOPICS[i % len(_TOPICS)]
    return Paper(
        title=f"{topic.title()} ({i})",
        abstract="A" * 300,
        authors=[f"Author{i}"],
        year=year,
        url=f"https://example.com/p{i}",
        source="arxiv",
        citation_count=10 + i,
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        content_hash=f"{i:064x}",
    )


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(
        llm=LLMConfig(
            host="http://localhost:11434",
            model="llama3.1:8b",
            temperature=0.0,
            num_ctx=4096,
        ),
        llm_screen=LLMScreenConfig(
            enabled=False,  # Disable screen for simpler test
            host="http://localhost:11434",
            model="llama3.2:3b",
        ),
        retrieval=RetrievalConfig(
            min_abstract_chars=10,
            max_age_years=10,
            title_dedup_threshold=85,  # int 50-100
            llm_shortlist_size=10,
            screen_shortlist_size=30,
        ),
        scoring=ScoringConfig(
            weights={
                "llm_relevance": 0.5,
                "citations": 0.3,
                "recency": 0.15,
                "source_diversity_bonus": 0.05,
            },
            min_acceptable_score=0.0,
            diversity_lambda=0.6,
        ),
        sources=SourcesConfig(
            arxiv=SourceConfig(enabled=True, max_candidates_per_subcategory=20),
            semantic_scholar=SourceConfig(enabled=True, max_candidates_per_subcategory=20),
            openalex=SourceConfig(enabled=True, max_candidates_per_subcategory=20),
            papers_with_code=SourceConfig(enabled=True, max_candidates_per_subcategory=20),
            ssrn=SourceConfig(enabled=True, max_candidates_per_subcategory=20),
            google_scholar=SourceConfig(enabled=False, max_candidates_per_subcategory=20),
        ),
        runtime=RuntimeConfig(
            concurrency=4,
            per_request_timeout_seconds=30,
            cache_directory="/tmp",
            audit_log_path="/tmp/audit.jsonl",
        ),
        output=OutputConfig(directory="/tmp"),
    )


@pytest.fixture
def category() -> Category:
    return Category(
        id="technical",
        name="Technical Risks",
        subcategories=[
            Subcategory(name="Hallucinations", keywords=["LLM"], target_papers=3),
        ],
    )


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_basic_flow(config: AppConfig, category: Category):
    """All sources return papers, judge scores them, runner produces results."""
    subcategory = category.subcategories[0]
    sources = [
        FakeSource("arxiv", [_make_paper(1), _make_paper(2)]),
        FakeSource("semantic_scholar", [_make_paper(3)]),
    ]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    assert result.subcategory_name == "Hallucinations"
    assert result.candidate_count == 3
    assert len(result.selected_papers) <= 3  # target_papers=3
    assert all(sp.composite_score > 0 for sp in result.selected_papers)


@pytest.mark.asyncio
async def test_runner_handles_source_failure_gracefully(config: AppConfig, category: Category):
    """If one source raises, the runner still produces results from the others."""
    subcategory = category.subcategories[0]
    sources = [
        FakeSource("arxiv", [_make_paper(1), _make_paper(2)]),
        FailingSource("broken_source"),
        FakeSource("openalex", [_make_paper(3)]),
    ]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    assert result.candidate_count == 3
    assert len(result.selected_papers) > 0


@pytest.mark.asyncio
async def test_runner_handles_all_sources_failing(config: AppConfig, category: Category):
    """If every source fails, runner produces an empty result without crashing."""
    subcategory = category.subcategories[0]
    sources = [FailingSource("a"), FailingSource("b")]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    assert result.candidate_count == 0
    assert result.selected_papers == []


@pytest.mark.asyncio
async def test_runner_filters_by_min_abstract_length(config: AppConfig, category: Category):
    """Papers with abstracts below min_abstract_chars must be dropped pre-judge."""
    subcategory = category.subcategories[0]
    config.retrieval.min_abstract_chars = 1000
    sources = [FakeSource("arxiv", [_make_paper(1), _make_paper(2)])]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    # All test papers have abstract="A"*300; below 1000 → all filtered
    assert result.candidate_count == 0


@pytest.mark.asyncio
async def test_runner_filters_by_max_age(config: AppConfig, category: Category):
    """Papers older than max_age_years must be dropped."""
    subcategory = category.subcategories[0]
    config.retrieval.max_age_years = 5
    current_year = datetime.now(UTC).year
    sources = [
        FakeSource(
            "arxiv",
            [
                _make_paper(1, year=current_year),  # in range
                _make_paper(2, year=current_year - 10),  # too old
            ],
        )
    ]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    assert result.candidate_count == 1


@pytest.mark.asyncio
async def test_runner_dedups_across_sources(config: AppConfig, category: Category):
    """The same paper returned by two sources should appear once."""
    subcategory = category.subcategories[0]
    shared = _make_paper(1)
    sources = [
        FakeSource("arxiv", [shared, _make_paper(2)]),
        FakeSource("openalex", [shared, _make_paper(3)]),  # duplicate
    ]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    # 4 returned, 1 dup → 3 unique
    assert result.candidate_count == 3


@pytest.mark.asyncio
async def test_runner_respects_target_papers(config: AppConfig, category: Category):
    """If subcategory.target_papers = 2, only 2 should be selected."""
    subcategory = Subcategory(name="Hallucinations", keywords=[], target_papers=2)
    sources = [
        FakeSource("arxiv", [_make_paper(i) for i in range(10)]),
    ]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    assert len(result.selected_papers) == 2


@pytest.mark.asyncio
async def test_runner_drops_papers_below_min_score(config: AppConfig, category: Category):
    """Papers scoring below min_acceptable_score must be dropped."""
    subcategory = category.subcategories[0]
    config.scoring.min_acceptable_score = 9.5  # very high
    sources = [
        FakeSource("arxiv", [_make_paper(i) for i in range(5)]),
    ]
    # Fake judge returns ~7.0 which is below 9.5
    judge = FakeJudge(base_score=7.0)

    result = await run_subcategory(category, subcategory, sources, judge, config)

    # Composite score depends on weights, but min_acceptable filters on composite.
    # With base 7.0 LLM and small citation contribution, composite stays <9.5
    # → all dropped.
    assert len(result.selected_papers) == 0


@pytest.mark.asyncio
async def test_runner_handles_judge_returning_none(config: AppConfig, category: Category):
    """If judge.score returns None (parse failure), paper is dropped."""
    subcategory = category.subcategories[0]

    class NullingJudge:
        async def score(self, paper, subcategory):
            return None  # always-failing judge

    sources = [FakeSource("arxiv", [_make_paper(i) for i in range(3)])]

    result = await run_subcategory(category, subcategory, sources, NullingJudge(), config)

    # All papers reach shortlist but none survive judging → no selection
    assert len(result.selected_papers) == 0
    assert result.candidate_count == 3


@pytest.mark.asyncio
async def test_runner_records_candidate_and_shortlist_counts(config: AppConfig, category: Category):
    """Counts on the SubcategoryResult must reflect actual pipeline state."""
    subcategory = category.subcategories[0]
    config.retrieval.llm_shortlist_size = 5
    sources = [
        FakeSource("arxiv", [_make_paper(i) for i in range(20)]),
    ]
    judge = FakeJudge()

    result = await run_subcategory(category, subcategory, sources, judge, config)

    assert result.candidate_count == 20
    assert result.shortlist_count == 5  # capped to llm_shortlist_size
