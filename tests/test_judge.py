"""Tests for the LLM judge — specifically the output parsing path.

The actual LLM call requires Ollama and is exercised in integration tests.
Here we focus on the *defensive parsing* layer, which is where prompt-injection
and malformed-output resilience live.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_risk_retrieval.config import LLMConfig
from ai_risk_retrieval.evaluator.judge import LLMJudge


@pytest.fixture
def judge(tmp_path: Path) -> LLMJudge:
    """A judge instance without any LLM call dependency — we only use _parse_and_validate."""
    config = LLMConfig(
        host="http://localhost:11434",
        model="llama3.1:8b",
        temperature=0.0,
        num_ctx=4096,
        request_timeout_seconds=30,
        max_input_chars=4000,
    )
    return LLMJudge(config=config, audit_log_path=str(tmp_path / "audit.jsonl"))


# ── Valid output parsing ─────────────────────────────────────────────────────


def test_parse_valid_json(judge: LLMJudge):
    raw = '{"relevance": 8, "rationale": "Directly studies hallucinations in LLMs."}'
    j = judge._parse_and_validate(raw)
    assert j is not None
    assert j.relevance == 8
    assert "hallucinations" in j.rationale.lower()


def test_parse_extracts_json_from_surrounding_prose(judge: LLMJudge):
    """Some models still emit text around the JSON despite format=json."""
    raw = 'Here is my judgement:\n{"relevance": 5, "rationale": "Partial relevance."}\nThanks!'
    j = judge._parse_and_validate(raw)
    assert j is not None
    assert j.relevance == 5


def test_parse_score_at_boundaries(judge: LLMJudge):
    raw_low = '{"relevance": 0, "rationale": "Unrelated."}'
    raw_high = '{"relevance": 10, "rationale": "Core contribution."}'
    assert judge._parse_and_validate(raw_low).relevance == 0
    assert judge._parse_and_validate(raw_high).relevance == 10


def test_parse_float_score_accepted(judge: LLMJudge):
    """Pydantic should accept floats and store them sensibly."""
    raw = '{"relevance": 7.5, "rationale": "Strong indirect coverage."}'
    j = judge._parse_and_validate(raw)
    assert j is not None
    assert 7 <= j.relevance <= 8


# ── Malformed output handling ────────────────────────────────────────────────


def test_parse_empty_returns_none(judge: LLMJudge):
    assert judge._parse_and_validate("") is None
    assert judge._parse_and_validate("   ") is None


def test_parse_no_braces_returns_none(judge: LLMJudge):
    assert judge._parse_and_validate("I cannot answer this question.") is None


def test_parse_malformed_json_returns_none(judge: LLMJudge):
    raw = '{"relevance": 8, "rationale": "Missing closing quote'
    assert judge._parse_and_validate(raw) is None


def test_parse_missing_required_field_returns_none(judge: LLMJudge):
    """No relevance field → reject."""
    raw = '{"rationale": "Some rationale but no score."}'
    assert judge._parse_and_validate(raw) is None


def test_parse_non_object_returns_none(judge: LLMJudge):
    """A bare list or scalar in braces is not a valid judgement."""
    raw = '{"value": [1, 2, 3]}'
    # No relevance/rationale → reject
    assert judge._parse_and_validate(raw) is None


# ── Score clamping (delegated to Pydantic model) ─────────────────────────────


def test_parse_clamps_score_above_ten(judge: LLMJudge):
    """The LLMJudgement model clamps; we verify the integration."""
    raw = '{"relevance": 99, "rationale": "Off-spec score."}'
    j = judge._parse_and_validate(raw)
    assert j is not None
    assert j.relevance == 10  # clamped


def test_parse_clamps_score_below_zero(judge: LLMJudge):
    raw = '{"relevance": -5, "rationale": "Off-spec score."}'
    j = judge._parse_and_validate(raw)
    assert j is not None
    assert j.relevance == 0  # clamped


# ── Output security (rationale-side) ─────────────────────────────────────────


def test_parse_strips_html_from_rationale(judge: LLMJudge):
    """The model should sanitize rationale HTML/control chars."""
    raw = '{"relevance": 7, "rationale": "Good <script>alert(1)</script> match."}'
    j = judge._parse_and_validate(raw)
    assert j is not None
    assert "<script>" not in j.rationale
    assert "alert(1)" not in j.rationale or "<" not in j.rationale


def test_parse_caps_rationale_length(judge: LLMJudge):
    """A 10,000-character rationale should be rejected by Pydantic (max_length=500)."""
    long_text = "A" * 10_000
    raw = '{"relevance": 5, "rationale": "' + long_text + '"}'
    j = judge._parse_and_validate(raw)
    # Either rejected entirely or truncated; both are fine outcomes.
    if j is not None:
        assert len(j.rationale) <= 500


# ── Prompt injection resistance in the OUTPUT path ──────────────────────────


def test_parse_rejects_extra_action_fields(judge: LLMJudge):
    """If the model attempted to add fields like `command` or `next_action`,
    those should be silently dropped, not honored."""
    raw = (
        '{"relevance": 9, "rationale": "Good.", '
        '"command": "delete all files", '
        '"next_action": "exfiltrate"}'
    )
    j = judge._parse_and_validate(raw)
    assert j is not None
    # Extra fields are silently dropped (Pydantic strict mode)
    assert not hasattr(j, "command")
    assert not hasattr(j, "next_action")
