"""Tests for MMR diversification (pipeline/diversify.py)."""

from datetime import UTC, datetime

from ai_risk_retrieval.models import LLMJudgement, Paper, ScoredPaper
from ai_risk_retrieval.pipeline.diversify import (
    _compute_tfidf_vectors,
    _cosine,
    _tokenize,
    mmr_select,
)

# ─── Fixture helper ─────────────────────────────────────────────────────────


def _scored(
    title: str,
    abstract: str,
    score: float,
    source: str = "arxiv",
) -> ScoredPaper:
    paper = Paper(
        title=title,
        abstract=abstract,
        url=f"https://example.com/{title.replace(' ', '_')}",
        source=source,  # type: ignore[arg-type]
        fetched_at=datetime.now(UTC),
        content_hash="a" * 64,
    )
    return ScoredPaper(
        paper=paper,
        llm=LLMJudgement(relevance=score, rationale="test"),
        composite_score=score,
    )


# ─── Tokenization & TF-IDF building blocks ──────────────────────────────────


def test_tokenize_strips_stopwords_and_punctuation():
    toks = _tokenize("The novel jailbreak attack on LLMs.")
    # Stopwords ("the", "on"), punctuation, and short tokens excluded.
    assert "the" not in toks
    assert "on" not in toks
    assert "novel" in toks
    assert "jailbreak" in toks
    assert "attack" in toks
    assert "llms" in toks


def test_tokenize_keeps_hyphens():
    """Compound terms common in ML literature should survive tokenization."""
    toks = _tokenize("fine-tuning large-language-models")
    assert "fine-tuning" in toks
    assert "large-language-models" in toks


def test_tfidf_vectors_are_l2_normalized():
    """Each vector must satisfy sum(w^2) ≈ 1 for cosine to equal dot product."""
    docs = ["jailbreak attack llm safety", "prompt injection llm defense", "unrelated topic"]
    vecs = _compute_tfidf_vectors(docs)
    for v in vecs:
        if v:  # empty vectors are fine
            norm_sq = sum(w * w for w in v.values())
            assert abs(norm_sq - 1.0) < 1e-9, f"vector not normalized: {norm_sq}"


def test_cosine_identical_docs_is_one():
    """Same text → cosine = 1.0 (L2-normalized vectors)."""
    vecs = _compute_tfidf_vectors(["jailbreak attack", "jailbreak attack"])
    assert abs(_cosine(vecs[0], vecs[1]) - 1.0) < 1e-9


def test_cosine_disjoint_docs_is_zero():
    """No shared terms → cosine = 0."""
    vecs = _compute_tfidf_vectors(["jailbreak attack", "completely different vocabulary"])
    assert _cosine(vecs[0], vecs[1]) == 0.0


def test_cosine_empty_vectors_safe():
    assert _cosine({}, {"a": 1.0}) == 0.0
    assert _cosine({"a": 1.0}, {}) == 0.0


# ─── MMR core behavior ─────────────────────────────────────────────────────


def test_mmr_empty_input():
    assert mmr_select([], target=3) == []


def test_mmr_first_pick_is_highest_scoring():
    """No matter what λ is, the first slot goes to the top score."""
    papers = [
        _scored("low", "filler", 5.0),
        _scored("high", "filler", 9.5),
        _scored("mid", "filler", 7.0),
    ]
    for lam in [0.0, 0.5, 1.0]:
        result = mmr_select(papers, target=1, lam=lam)
        assert len(result) == 1
        assert result[0].paper.title == "high", f"failed at λ={lam}"


def test_mmr_lambda_one_matches_pure_score_order():
    """λ=1 turns off the diversity penalty — pure ranking by composite score."""
    papers = [
        _scored("a", "shared shared shared vocabulary", 9.0),
        _scored("b", "shared shared shared vocabulary", 8.5),  # near-duplicate of a
        _scored("c", "totally different terms here", 8.0),
    ]
    result = mmr_select(papers, target=3, lam=1.0)
    assert [p.paper.title for p in result] == ["a", "b", "c"]


def test_mmr_demotes_near_duplicates_at_low_lambda():
    """
    The headline MMR behavior. Three papers: a and b are near-duplicates with
    a slightly higher than b; c is distinct but lower-scoring. Pure score
    would pick a, b. MMR should prefer a, c — the distinct alternative.
    """
    papers = [
        _scored(
            "a",
            "jailbreak attack llm prompt injection safety bypass evaluation",
            9.0,
        ),
        _scored(
            "b",
            "jailbreak attack llm prompt injection safety bypass benchmark",  # near-dup of a
            8.5,
        ),
        _scored(
            "c",
            "data poisoning backdoor attack supply chain machine learning",
            7.5,
        ),
    ]
    result = mmr_select(papers, target=2, lam=0.5)
    titles = [p.paper.title for p in result]
    assert titles[0] == "a"  # highest score always wins slot 1
    assert titles[1] == "c"  # MMR should pick the distinct one over the near-dup


def test_mmr_target_larger_than_input():
    """Asking for more than is available returns all of them, ordered by MMR."""
    papers = [_scored("a", "x y z", 7.0), _scored("b", "u v w", 6.0)]
    result = mmr_select(papers, target=10, lam=0.6)
    assert len(result) == 2
    assert {p.paper.title for p in result} == {"a", "b"}


def test_mmr_target_zero():
    papers = [_scored("a", "x", 5.0)]
    assert mmr_select(papers, target=0) == []


def test_mmr_lambda_clamped():
    """Out-of-range λ should silently clamp rather than crash."""
    papers = [_scored("a", "x y z", 9.0), _scored("b", "x y z", 8.0)]
    # Clamped to 1.0
    result = mmr_select(papers, target=2, lam=5.0)
    assert [p.paper.title for p in result] == ["a", "b"]
    # Clamped to 0.0 — relevance ignored, only novelty matters; first pick is
    # still highest score (set S is empty), but second pick depends on similarity.
    result2 = mmr_select(papers, target=2, lam=-1.0)
    assert len(result2) == 2
