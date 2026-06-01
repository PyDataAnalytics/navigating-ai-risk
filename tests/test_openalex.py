"""
Tests for the OpenAlex source — specifically the abstract reconstruction
from inverted-index format, which is the only non-trivial logic in the
adapter and the most likely thing to silently produce garbage if it breaks.
"""

from ai_risk_retrieval.sources.openalex import OpenAlexSource


def test_reconstruct_abstract_basic():
    """Inverted index → flat text, positions in any order."""
    inverted = {
        "We": [0],
        "propose": [1],
        "a": [2, 5],
        "novel": [3],
        "method": [4],
        "for": [6],
        "evaluation": [7],
    }
    text = OpenAlexSource._reconstruct_abstract(inverted)
    assert text == "We propose a novel method a for evaluation"


def test_reconstruct_abstract_with_repeats():
    """A word appearing at multiple positions reconstructs at each."""
    inverted = {"the": [0, 3], "cat": [1, 4], "sat": [2]}
    text = OpenAlexSource._reconstruct_abstract(inverted)
    assert text == "the cat sat the cat"


def test_reconstruct_abstract_empty_input():
    assert OpenAlexSource._reconstruct_abstract(None) == ""
    assert OpenAlexSource._reconstruct_abstract({}) == ""


def test_reconstruct_abstract_handles_gaps():
    """If positions are sparse, the gaps are dropped (no empty-string leakage)."""
    inverted = {"first": [0], "last": [10]}
    text = OpenAlexSource._reconstruct_abstract(inverted)
    # Empty slots should not appear as visible blanks
    assert text == "first last"


def test_reconstruct_abstract_ignores_garbage_types():
    """A hostile/malformed response shouldn't crash; just produce best-effort text."""
    inverted = {
        "good": [0],
        "bad": "not a list",  # malformed
        "alsogood": [2],
        123: [1],  # non-string key
    }
    text = OpenAlexSource._reconstruct_abstract(inverted)  # type: ignore[arg-type]
    # "good" at 0 and "alsogood" at 2 should be present; bad/123 silently dropped
    assert "good" in text
    assert "alsogood" in text
    assert "bad" not in text
