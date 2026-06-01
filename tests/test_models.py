"""Tests for strict LLM output validation."""

import pytest
from pydantic import ValidationError

from ai_risk_retrieval.models import LLMJudgement, Subcategory


def test_valid_judgement():
    j = LLMJudgement(relevance=7.5, rationale="Directly studies the topic.")
    assert j.relevance == 7.5
    assert "Directly" in j.rationale


def test_score_clamped_below_zero():
    with pytest.raises(ValidationError):
        LLMJudgement(relevance=-1.0, rationale="x")


def test_score_clamped_above_ten():
    """A compromised model trying to return 99.9 must be rejected."""
    with pytest.raises(ValidationError):
        LLMJudgement(relevance=99.9, rationale="x")


def test_rationale_length_capped():
    with pytest.raises(ValidationError):
        LLMJudgement(relevance=5.0, rationale="x" * 5000)


def test_rationale_html_stripped():
    j = LLMJudgement(relevance=5.0, rationale="A <script>alert(1)</script> paper.")
    assert "<script>" not in j.rationale
    assert "alert(1)" in j.rationale or "A" in j.rationale


def test_rationale_control_chars_stripped():
    j = LLMJudgement(relevance=5.0, rationale="text\x00with\x07control")
    assert "\x00" not in j.rationale
    assert "\x07" not in j.rationale


def test_extra_fields_in_input_are_ignored():
    """Compromised model adding extra fields shouldn't break parsing."""
    j = LLMJudgement.model_validate({"relevance": 5.0, "rationale": "ok", "command": "rm -rf /"})
    assert j.relevance == 5.0
    # `command` doesn't end up on the model
    assert not hasattr(j, "command")


def test_subcategory_accepts_excludes():
    """Negative anchors field stores list of exclusion phrases."""
    s = Subcategory(
        name="Hallucinations",
        keywords=["LLM hallucination"],
        excludes=["medical hallucinations", "perceptual hallucinations"],
    )
    assert len(s.excludes) == 2
    assert "medical hallucinations" in s.excludes


def test_subcategory_excludes_default_empty():
    s = Subcategory(name="Test")
    assert s.excludes == []


def test_subcategory_excludes_capped():
    """Bounded to keep the judge prompt size predictable."""
    with pytest.raises(ValidationError):
        Subcategory(name="Test", excludes=[f"exclude {i}" for i in range(15)])
