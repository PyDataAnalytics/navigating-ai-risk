"""Layer 1 quality audits for the taxonomy.

These tests check the *content quality* of subcategory_definitions.yaml,
distinct from the structural integrity tests in test_adjacencies.py.

Each audit fails the build on a real regression and passes otherwise. The
tests are intentionally strict — we want CI red on the first quality slip,
not a warning that gets ignored.

Audits:
    A2 — Disambiguation word-count distribution: no category drifts to
         short, formulaic lines.
    A3 — applies_when / does_not_apply_when must not overlap.
    A5 — Every entry has at least 3 user_signals.
    A6 — No near-identical one_lines within a similar-cluster (which would
         mean two entries are too close to disambiguate).
    A7 — Every disambiguation references its sibling by a substantive
         keyword from the sibling's name.
    A8 — Similar edges are symmetric: if A's similar contains B, B's similar
         must contain A.
"""

from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config"

# Threshold constants — codified here, easy to inspect and adjust.
MIN_DISAMBIG_MEDIAN_WORDS_PER_CAT = 14  # Below this, lines are likely formulaic
MIN_USER_SIGNALS_PER_ENTRY = 3
MAX_ONE_LINE_SIMILARITY_RATIO = 0.75  # 0..1; above this, two one_lines are too close


@pytest.fixture(scope="module")
def taxonomy():
    return yaml.safe_load((CONFIG / "taxonomy.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def definitions():
    return yaml.safe_load((CONFIG / "subcategory_definitions.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sub_to_cat(taxonomy):
    return {
        sub["name"]: cat["name"] for cat in taxonomy["categories"] for sub in cat["subcategories"]
    }


@pytest.fixture(scope="module")
def by_name(definitions):
    return {sc["name"]: sc for sc in definitions["subcategories"]}


# ---------------------------------------------------------------------------
# A2 — Disambiguation word-count distribution
# ---------------------------------------------------------------------------


def test_a2_disambig_word_count_by_category(definitions, sub_to_cat):
    """Median disambiguation word count per category must stay above floor.

    Catches the case where a future authoring pass produces short, formulaic
    disambiguations in one category while leaving others rich.
    """
    by_cat = defaultdict(list)
    for sc in definitions["subcategories"]:
        cat = sub_to_cat[sc["name"]]
        for text in sc.get("disambiguation", {}).values():
            by_cat[cat].append(len(text.split()))

    below_floor = []
    for cat, lengths in by_cat.items():
        if not lengths:
            continue
        sorted_l = sorted(lengths)
        median = sorted_l[len(sorted_l) // 2]
        if median < MIN_DISAMBIG_MEDIAN_WORDS_PER_CAT:
            below_floor.append((cat, median, len(lengths)))

    assert not below_floor, (
        f"Categories with disambig median below {MIN_DISAMBIG_MEDIAN_WORDS_PER_CAT}w: {below_floor}"
    )


# ---------------------------------------------------------------------------
# A3 — applies_when / does_not_apply_when overlap
# ---------------------------------------------------------------------------


def test_a3_applies_dna_no_overlap(definitions):
    """The same line cannot appear in both applies_when and does_not_apply_when.

    Catches authoring bugs where copy-paste produces contradictory entries.
    """
    overlaps = []
    for sc in definitions["subcategories"]:
        aw = set(sc["applies_when"])
        dna = set(sc["does_not_apply_when"])
        inter = aw & dna
        if inter:
            overlaps.append((sc["name"], list(inter)))
    assert not overlaps, f"applies_when/dna_when overlaps: {overlaps}"


# ---------------------------------------------------------------------------
# A5 — Minimum user_signals coverage
# ---------------------------------------------------------------------------


def test_a5_user_signals_minimum(definitions):
    """Every entry has at least N user_signals.

    The matcher uses user_signals as embedding-side text. Too few signals
    produces sparse retrieval coverage.
    """
    low = []
    for sc in definitions["subcategories"]:
        n_sig = len(sc.get("user_signals", []))
        if n_sig < MIN_USER_SIGNALS_PER_ENTRY:
            low.append((sc["name"], n_sig))
    assert not low, f"Entries with <{MIN_USER_SIGNALS_PER_ENTRY} user_signals: {low}"


# ---------------------------------------------------------------------------
# A6 — No near-identical one_lines within a similar-cluster
# ---------------------------------------------------------------------------


def test_a6_one_lines_distinct_within_similar_cluster(definitions, by_name):
    """Two entries linked as similar must have meaningfully different one_lines.

    If their one_lines are nearly identical, no disambiguation can help the
    matcher pick between them — the taxonomy itself is the bug.
    """
    collisions = []
    seen_pairs = set()
    for sc in definitions["subcategories"]:
        src = sc["name"]
        src_one = sc["one_line"]
        for sib in sc["adjacent_to"]["similar"]:
            pair = tuple(sorted([src, sib]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            sib_one = by_name[sib]["one_line"]
            ratio = SequenceMatcher(None, src_one, sib_one).ratio()
            if ratio > MAX_ONE_LINE_SIMILARITY_RATIO:
                collisions.append((src, sib, round(ratio, 2)))
    assert not collisions, (
        f"Near-identical one_lines within similar-cluster "
        f"(ratio > {MAX_ONE_LINE_SIMILARITY_RATIO}): {collisions}"
    )


# ---------------------------------------------------------------------------
# A7 — Disambiguations must reference the sibling
# ---------------------------------------------------------------------------


def test_a7_disambig_references_sibling(definitions):
    """Every disambiguation text must contain at least one substantive keyword
    from the sibling's name.

    Catches placeholder-like or generic disambiguation text that doesn't
    actually distinguish the pair.
    """
    GENERIC = {"the", "a", "an", "of", "in", "on", "for", "with", "and", "or", "by", "to"}
    bad = []
    for sc in definitions["subcategories"]:
        for sib, text in sc.get("disambiguation", {}).items():
            sib_words = [
                w.lower().rstrip(".,;")
                for w in sib.split()
                if len(w) > 3 and w.lower() not in GENERIC
            ]
            text_lower = text.lower()
            if sib_words and not any(w in text_lower for w in sib_words):
                bad.append((sc["name"], sib, text[:80]))
    assert not bad, f"Disambigs not referencing sibling: {bad}"


# ---------------------------------------------------------------------------
# A8 — Similar-edge symmetry
# ---------------------------------------------------------------------------


def test_a8_similar_edges_symmetric(definitions, by_name):
    """If A's adjacent_to.similar contains B, then B's adjacent_to.similar
    must contain A.

    'similar' is intrinsically symmetric. Asymmetric edges produce
    inconsistent matcher context — A is presented as a sibling of B in one
    direction but not the other.

    Pass A enforces this on regeneration; this test catches manual YAML
    edits that violate it.
    """
    asymmetric = []
    for sc in definitions["subcategories"]:
        a = sc["name"]
        for b in sc["adjacent_to"]["similar"]:
            if a not in by_name[b]["adjacent_to"]["similar"]:
                asymmetric.append((a, b))
    assert not asymmetric, f"Asymmetric similar edges (A→B but not B→A): {asymmetric}"
