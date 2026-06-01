"""Tests for config validation and security defaults."""

import pytest
from pydantic import ValidationError

from ai_risk_retrieval.config import LLMConfig, ScoringWeights


def test_remote_ollama_host_rejected():
    """Defense: refuse non-local Ollama hosts to prevent prompt-injection-driven exfiltration."""
    with pytest.raises(ValidationError, match="not local"):
        LLMConfig(model="llama3.1:8b", host="https://attacker.example.com:11434")


def test_local_ollama_host_accepted():
    cfg = LLMConfig(model="llama3.1:8b", host="http://127.0.0.1:11434")
    assert cfg.host.endswith("11434")


def test_localhost_accepted():
    cfg = LLMConfig(model="llama3.1:8b", host="http://localhost:11434")
    assert "localhost" in cfg.host


def test_scoring_weights_must_sum_to_one():
    with pytest.raises(ValidationError, match="must sum to 1"):
        ScoringWeights(
            llm_relevance=0.5,
            citations=0.5,
            recency=0.5,  # over by 0.5
            source_diversity_bonus=0.5,
        )


def test_scoring_weights_valid_when_summing_to_one():
    w = ScoringWeights(
        llm_relevance=0.65, citations=0.15, recency=0.15, source_diversity_bonus=0.05
    )
    assert w.llm_relevance == 0.65


def test_max_input_chars_has_upper_bound():
    """Defense: don't allow the operator to bypass the prompt size limit."""
    with pytest.raises(ValidationError):
        LLMConfig(model="x", host="http://localhost", max_input_chars=10_000_000)
