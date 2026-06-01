"""
Maximal Marginal Relevance (MMR) diversification.

Problem
-------
After composite scoring, the top papers are sorted by score and the top-N
are taken. This greedy selection can produce three near-duplicate papers
when the highest-scoring papers happen to be follow-ups, evaluations, or
extensions of the same prior work. The reader gets the same finding three
times instead of three complementary perspectives.

Solution
--------
MMR (Carbonell & Goldstein, 1998) selects the next paper as:

    next = argmax_p [ λ · score(p) - (1 - λ) · max_q∈S sim(p, q) ]

where S is the set of already-selected papers and sim is cosine similarity
on TF-IDF vectors of title + abstract. λ ∈ [0, 1] is the relevance-vs-
diversity dial: λ=1 collapses to pure score (the previous behavior),
λ=0.5–0.7 noticeably diversifies, λ→0 ignores relevance and surfaces oddities.

Concretely, this makes the top-3 *meaningfully different* picks while still
being among the strongest by composite score. A paper that's similar but
clearly the best on the topic still wins its slot; what gets demoted is
the *similar-AND-lower-scoring* paper that would otherwise crowd out a
distinct alternative.

We deliberately avoid scikit-learn or other ML deps and hand-roll TF-IDF
cosine. The vocabulary per call is tiny (3–20 documents) so the perf
difference is irrelevant, and adding a heavy dep for ~80 lines of well-
understood math is poor engineering.

The L2 norm and IDF formulas here are the standard textbook ones; see
e.g. Manning, Raghavan & Schütze ch. 6. Cosine similarity is in [0, 1]
for non-negative TF-IDF vectors, which makes the MMR penalty well-behaved.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from ..models import ScoredPaper

# Minimal English stopword set — keeps cosine similarity from being dominated
# by function words. Not a complete stopword list (deliberately so — papers
# in adjacent fields share more function words than content words, and we
# want the *content* signal to drive similarity).
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "as",
        "and",
        "or",
        "but",
        "not",
        "no",
        "this",
        "that",
        "these",
        "those",
        "we",
        "our",
        "us",
        "i",
        "it",
        "its",
        "they",
        "their",
        "them",
        "he",
        "she",
        "his",
        "her",
        "from",
        "into",
        "about",
        "than",
        "then",
        "so",
        "if",
        "when",
        "while",
        "such",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "can",
        "could",
        "may",
        "might",
        "will",
        "would",
        "should",
        "shall",
        "show",
        "shown",
        "shows",
        "showing",
        "paper",
        "papers",
        "study",
        "studies",
        "studied",
        "method",
        "methods",
        "approach",
        "approaches",
        "result",
        "results",
        "find",
        "finds",
        "found",
        "use",
        "used",
        "using",
        "based",
        "propose",
        "proposed",
        "proposes",
    }
)

# Token = letters/digits/hyphens, length ≥ 3. Drops punctuation and very
# short noise like "a", "of" without relying on stopwords alone.
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]{2,}")


def _tokenize(text: str) -> list[str]:
    """Lowercase, regex-tokenize, drop stopwords."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _doc_text(sp: ScoredPaper) -> str:
    """Concatenate the fields that define what a paper is *about*."""
    return f"{sp.paper.title} {sp.paper.abstract}"


def _compute_tfidf_vectors(docs: list[str]) -> list[dict[str, float]]:
    """
    Compute L2-normalized TF-IDF vectors as sparse dicts {term: weight}.

    Sparse dicts are the right representation when each doc has tens to
    hundreds of unique terms out of a vocab of maybe a thousand across
    the whole batch — much cheaper than dense vectors over the union.
    """
    if not docs:
        return []
    tokenized = [_tokenize(d) for d in docs]
    n_docs = len(docs)

    # Document frequency: how many docs contain each term
    df: Counter[str] = Counter()
    for toks in tokenized:
        for t in set(toks):
            df[t] += 1

    # IDF with smoothing (add-one) so a term in every doc still has small
    # nonzero weight rather than becoming exactly 0 and discarded.
    # log(1 + N / (1 + df)) is one of the standard variants.
    idf = {t: math.log(1.0 + n_docs / (1.0 + dfi)) for t, dfi in df.items()}

    vectors: list[dict[str, float]] = []
    for toks in tokenized:
        if not toks:
            vectors.append({})
            continue
        tf = Counter(toks)
        # Raw TF-IDF weights
        vec = {t: count * idf.get(t, 0.0) for t, count in tf.items()}
        # L2-normalize so cosine = dot product. Skip zero vectors safely.
        norm = math.sqrt(sum(w * w for w in vec.values()))
        if norm > 0:
            vec = {t: w / norm for t, w in vec.items()}
        vectors.append(vec)
    return vectors


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity of two L2-normalized sparse vectors. Returns [0, 1]."""
    if not v1 or not v2:
        return 0.0
    # Iterate over the smaller vector for efficiency
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(w * v2.get(t, 0.0) for t, w in v1.items())


# ─── Public API ─────────────────────────────────────────────────────────────


def mmr_select(
    candidates: list[ScoredPaper],
    target: int,
    lam: float = 0.6,
) -> list[ScoredPaper]:
    """
    Select `target` papers using Maximal Marginal Relevance.

    Args:
        candidates: ScoredPapers, in any order. Should already have a
            composite_score on each.
        target: how many to select.
        lam: relevance vs diversity tradeoff. 1.0 = pure score (no
            diversification, equivalent to sorting by composite_score and
            slicing). 0.0 = pure novelty (ignore score, maximize spread).
            0.5–0.7 is the practical range. 0.6 is a sensible default.

    Returns:
        Selected papers in the order MMR chose them. The first pick is
        always the highest-scoring candidate (since S is empty, the
        diversity term is 0); subsequent picks balance score against
        dissimilarity to what's already selected.

    Edge cases:
        - Empty input → empty output.
        - target >= len(candidates) → all candidates returned, ordered by
          MMR (which still differs from pure score order).
        - lam outside [0, 1] is clamped silently. The composite_score range
          is already [0, 10] and cosine is in [0, 1], so we rescale cosine
          to [0, 10] internally to keep the two terms comparable.
    """
    if not candidates or target <= 0:
        return []
    lam = max(0.0, min(1.0, lam))
    target = min(target, len(candidates))

    # Build TF-IDF vectors once, in the same order as candidates
    vectors = _compute_tfidf_vectors([_doc_text(sp) for sp in candidates])

    selected_idx: list[int] = []
    remaining_idx = list(range(len(candidates)))

    # First pick: highest composite score, no diversity penalty applies.
    first = max(remaining_idx, key=lambda i: candidates[i].composite_score)
    selected_idx.append(first)
    remaining_idx.remove(first)

    # Subsequent picks
    while len(selected_idx) < target and remaining_idx:
        best_score = -math.inf
        best_idx = remaining_idx[0]
        for i in remaining_idx:
            relevance = candidates[i].composite_score  # [0, 10]
            # Max similarity to any already-selected paper. Rescale to [0, 10]
            # so the diversity term is comparable to relevance.
            max_sim = max(_cosine(vectors[i], vectors[j]) for j in selected_idx)
            mmr = lam * relevance - (1.0 - lam) * (max_sim * 10.0)
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        selected_idx.append(best_idx)
        remaining_idx.remove(best_idx)

    return [candidates[i] for i in selected_idx]
