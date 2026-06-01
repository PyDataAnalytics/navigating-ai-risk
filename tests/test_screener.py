"""
Tests for the BinaryScreener parser.

The async screen() method requires Ollama; these tests focus on
_parse_and_validate, which is the pure-Python validation surface that decides
whether a screen response is trustworthy.
"""

from ai_risk_retrieval.config import LLMScreenConfig
from ai_risk_retrieval.evaluator.screener import BinaryScreener, ScreenResult


def _make_screener(tmp_path) -> BinaryScreener:
    cfg = LLMScreenConfig(enabled=True, model="llama3.2:3b", host="http://localhost:11434")
    return BinaryScreener(config=cfg, audit_log_path=str(tmp_path / "audit.jsonl"))


# ─── Parse: happy path ──────────────────────────────────────────────────────


def test_parse_valid_true(tmp_path):
    s = _make_screener(tmp_path)
    r = s._parse_and_validate('{"relevant": true, "reason": "directly studies it"}')
    assert isinstance(r, ScreenResult)
    assert r.relevant is True
    assert "directly" in r.reason


def test_parse_valid_false(tmp_path):
    s = _make_screener(tmp_path)
    r = s._parse_and_validate('{"relevant": false}')
    assert r.relevant is False
    assert r.reason == ""


def test_parse_extracts_from_surrounding_prose(tmp_path):
    """Cheap models often emit chatty wrappers around the JSON block."""
    s = _make_screener(tmp_path)
    r = s._parse_and_validate(
        'Sure! Here\'s my answer: {"relevant": true} Let me know if you need more.'
    )
    assert r.relevant is True


# ─── Parse: string-boolean coercion (small models often return these) ───────


def test_parse_coerces_string_true(tmp_path):
    s = _make_screener(tmp_path)
    for variant in [
        '{"relevant": "true"}',
        '{"relevant": "True"}',
        '{"relevant": "yes"}',
        '{"relevant": "YES"}',
        '{"relevant": "1"}',
    ]:
        r = s._parse_and_validate(variant)
        assert r is not None and r.relevant is True, variant


def test_parse_coerces_string_false(tmp_path):
    s = _make_screener(tmp_path)
    for variant in ['{"relevant": "false"}', '{"relevant": "No"}', '{"relevant": "0"}']:
        r = s._parse_and_validate(variant)
        assert r is not None and r.relevant is False, variant


def test_parse_rejects_ambiguous_string(tmp_path):
    """A string that isn't a clear boolean → None → caller treats as 'let it through'."""
    s = _make_screener(tmp_path)
    assert s._parse_and_validate('{"relevant": "maybe"}') is None


# ─── Parse: failure modes (must return None) ────────────────────────────────


def test_parse_empty_returns_none(tmp_path):
    s = _make_screener(tmp_path)
    assert s._parse_and_validate("") is None


def test_parse_no_json_returns_none(tmp_path):
    s = _make_screener(tmp_path)
    assert s._parse_and_validate("just prose, no JSON") is None


def test_parse_malformed_json_returns_none(tmp_path):
    s = _make_screener(tmp_path)
    assert s._parse_and_validate('{"relevant": true,,,,}') is None


def test_parse_missing_field_returns_none(tmp_path):
    """Without `relevant`, the screen can't make a decision."""
    s = _make_screener(tmp_path)
    assert s._parse_and_validate('{"reason": "looks topical"}') is None


def test_parse_non_object_returns_none(tmp_path):
    s = _make_screener(tmp_path)
    assert s._parse_and_validate('"just a string"') is None


# ─── Reason length cap ──────────────────────────────────────────────────────


def test_reason_length_capped(tmp_path):
    """Schema enforces reason ≤ 200 chars; oversized values rejected."""
    s = _make_screener(tmp_path)
    long_reason = "x" * 500
    assert s._parse_and_validate(f'{{"relevant": true, "reason": "{long_reason}"}}') is None
