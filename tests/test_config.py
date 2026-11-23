"""Tests for config validation and security defaults."""

import pytest
from pydantic import ValidationError

from ai_risk_retrieval.config import (
    AppConfig,
    LLMConfig,
    LLMScreenConfig,
    OutputConfig,
    RetrievalConfig,
    RuntimeConfig,
    ScoringConfig,
    ScoringWeights,
    SourceConfig,
    SourcesConfig,
)


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


# --- Regression: "ollama"-prefixed remote hosts must not pass the local check -


@pytest.mark.parametrize(
    "host",
    [
        "http://ollama.attacker.example.com:11434",
        "http://ollama-exfil.evil.io/",
        "https://ollama.cloud-provider.net:443",
    ],
)
def test_ollama_prefixed_remote_host_rejected(host):
    """
    A dotted hostname is public DNS, not a local instance. An earlier check used
    host.startswith("ollama"), which accepted every host above and defeated the
    exfiltration defense the validator exists to provide.
    """
    with pytest.raises(ValidationError, match="not local"):
        LLMConfig(model="llama3.1:8b", host=host)


@pytest.mark.parametrize("host", ["http://ollama:11434", "http://ollama-judge:11434"])
def test_dotless_container_service_name_accepted(host):
    """Docker Compose / Kubernetes service names stay usable."""
    cfg = LLMConfig(model="llama3.1:8b", host=host)
    assert cfg.host == host


def test_screen_host_shares_the_hardened_check():
    """The screener config must not carry its own weaker copy of the host rule."""
    with pytest.raises(ValidationError, match="not local"):
        LLMScreenConfig(enabled=True, host="http://ollama.attacker.example.com:11434")


# --- Cross-field: screen pool must cover the judge's shortlist ----------------


def _app_config(*, screen_enabled: bool, screen_size: int, shortlist: int) -> AppConfig:
    src = SourceConfig(enabled=True, max_candidates_per_subcategory=20)
    return AppConfig(
        llm=LLMConfig(host="http://localhost:11434", model="llama3.1:8b"),
        llm_screen=LLMScreenConfig(
            enabled=screen_enabled, host="http://localhost:11434", model="llama3.2:3b"
        ),
        retrieval=RetrievalConfig(llm_shortlist_size=shortlist, screen_shortlist_size=screen_size),
        scoring=ScoringConfig(
            weights=ScoringWeights(
                llm_relevance=0.65,
                citations=0.15,
                recency=0.15,
                source_diversity_bonus=0.05,
            )
        ),
        sources=SourcesConfig(
            arxiv=src,
            semantic_scholar=src,
            papers_with_code=src,
            ssrn=src,
            google_scholar=src,
            openalex=src,
        ),
        output=OutputConfig(directory="/tmp"),
        runtime=RuntimeConfig(cache_directory="/tmp", audit_log_path="/tmp/audit.jsonl"),
    )


def test_screen_pool_smaller_than_shortlist_rejected():
    with pytest.raises(ValidationError, match="smaller than"):
        _app_config(screen_enabled=True, screen_size=5, shortlist=50)


def test_screen_pool_larger_than_shortlist_accepted():
    cfg = _app_config(screen_enabled=True, screen_size=50, shortlist=20)
    assert cfg.retrieval.screen_shortlist_size == 50


def test_screen_pool_not_checked_when_screen_disabled():
    """screen_shortlist_size is ignored in single-stage mode, so it must not error."""
    cfg = _app_config(screen_enabled=False, screen_size=5, shortlist=50)
    assert cfg.llm_screen.enabled is False
