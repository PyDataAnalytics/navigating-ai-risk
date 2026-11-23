"""Config loading. Validates YAML against a schema and resolves secrets from env."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from .models import Taxonomy

# Hostnames treated as "the machine this process runs on".
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _require_local_host(value: str, label: str) -> str:
    """
    Reject any Ollama host that is not loopback or a container-local service
    name. Ollama is local-only by design here: reusing a networked instance
    exposes it to prompt-injection-driven exfiltration of other tenants' data.

    A bare, dotless hostname (``ollama``, ``ollama-judge``) is how Docker
    Compose and Kubernetes name a service on an internal network, so those are
    allowed. A dotted name is public DNS and is refused even when it begins
    with "ollama" - ``ollama.attacker.example.com`` is not a local host, and an
    earlier version of this check accepted it via ``startswith("ollama")``.
    """
    from urllib.parse import urlparse

    host = (urlparse(value).hostname or "").lower()
    is_loopback = host in _LOOPBACK_HOSTS
    is_service_name = host.startswith("ollama") and "." not in host
    if not (is_loopback or is_service_name):
        raise ValueError(
            f"{label} host {value!r} is not local. Use localhost/127.0.0.1, or a "
            "dotless container service name such as 'ollama'. Dotted hostnames are "
            "refused even when they start with 'ollama'; to target a remote "
            "instance, edit _require_local_host deliberately."
        )
    return value


class LLMConfig(BaseModel):
    provider: str = "ollama"
    host: str = "http://127.0.0.1:11434"
    model: str
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    num_ctx: int = Field(default=4096, ge=512, le=131072)
    request_timeout_seconds: int = Field(default=60, ge=5, le=600)
    max_input_chars: int = Field(default=6000, ge=500, le=50_000)

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, v: str) -> str:
        if v != "ollama":
            raise ValueError(
                f"Unknown LLM provider: {v!r}. Only 'ollama' is supported - "
                "this project runs every LLM step on a self-hosted model."
            )
        return v

    @field_validator("host")
    @classmethod
    def _validate_host(cls, v: str) -> str:
        return _require_local_host(v, "LLM")


class LLMScreenConfig(BaseModel):
    """
    Optional cheap-model relevance screener (stage 1 of two-stage judging).

    When `enabled=true`, an extended shortlist is filtered through a small
    LLM with a yes/no relevance prompt before the expensive detailed judge
    runs on survivors. The screen model can differ from the judge model -
    typical pairing is llama3.2:3b for the screen and llama3.1:8b for the
    judge. All other security defenses (host check, sanitization, schema
    validation, audit log) apply identically.
    """

    enabled: bool = False
    provider: str = "ollama"
    host: str = "http://127.0.0.1:11434"
    model: str = "llama3.2:3b"
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    num_ctx: int = Field(default=2048, ge=512, le=131072)
    request_timeout_seconds: int = Field(default=30, ge=5, le=600)
    max_input_chars: int = Field(default=4000, ge=500, le=50_000)

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, v: str) -> str:
        if v != "ollama":
            raise ValueError(f"Unknown LLM screen provider: {v!r}. Only 'ollama' is supported.")
        return v

    @field_validator("host")
    @classmethod
    def _validate_host(cls, v: str) -> str:
        return _require_local_host(v, "LLM screen")


class SourceConfig(BaseModel):
    enabled: bool = True
    max_candidates_per_subcategory: int = Field(default=20, ge=0, le=200)
    arxiv_categories: list[str] | None = None
    api_key_env: str | None = None

    def resolve_api_key(self) -> str | None:
        """Read API key from env at access time. Never stored on the model."""
        if not self.api_key_env:
            return None
        return os.environ.get(self.api_key_env)


class SourcesConfig(BaseModel):
    arxiv: SourceConfig
    semantic_scholar: SourceConfig
    papers_with_code: SourceConfig
    ssrn: SourceConfig
    google_scholar: SourceConfig
    openalex: SourceConfig


class RetrievalConfig(BaseModel):
    max_age_years: int | None = Field(default=6, ge=1, le=100)
    min_abstract_chars: int = Field(default=200, ge=0, le=10_000)
    title_dedup_threshold: int = Field(default=92, ge=50, le=100)
    # Number of papers sent to the expensive detailed judge per subcategory.
    llm_shortlist_size: int = Field(default=20, ge=3, le=100)
    # When the cheap screener is enabled (llm_screen.enabled=true), this is
    # the *extended* pool sent to the screen. Survivors of the screen are
    # then trimmed to `llm_shortlist_size` for detailed scoring. Effect:
    # better recall without raising compute on the expensive judge.
    # Ignored when llm_screen is disabled.
    screen_shortlist_size: int = Field(default=50, ge=5, le=300)


class ScoringWeights(BaseModel):
    llm_relevance: float = Field(ge=0.0, le=1.0)
    citations: float = Field(ge=0.0, le=1.0)
    recency: float = Field(ge=0.0, le=1.0)
    source_diversity_bonus: float = Field(ge=0.0, le=1.0)

    @field_validator("source_diversity_bonus")
    @classmethod
    def _sum_to_one(cls, v: float, info: Any) -> float:
        total = sum(info.data.values()) + v
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scoring weights must sum to 1.0; got {total}")
        return v


class ScoringConfig(BaseModel):
    weights: ScoringWeights
    min_acceptable_score: float = Field(default=4.0, ge=0.0, le=10.0)
    # MMR diversification lambda for final selection. 1.0 = pure composite
    # score (greedy top-N, the original behavior). 0.6 is the recommended
    # default for content diversity; 0.5 pushes harder toward variety; lower
    # than 0.3 starts surfacing oddities. See pipeline/diversify.py.
    diversity_lambda: float = Field(default=0.6, ge=0.0, le=1.0)
    # Flat penalty subtracted from an arXiv-sourced paper's composite score so
    # peer-reviewed venues outrank preprints of equal merit. arXiv is still
    # retrieved and kept - only demoted; 0.0 disables. Applied in
    # pipeline/rank.py via getattr, so configs lacking this field act as 0.0.
    arxiv_penalty: float = Field(default=0.5, ge=0.0, le=10.0)


class OutputConfig(BaseModel):
    directory: str = "data/output"
    format: str = Field(default="json", pattern=r"^(json)$")
    include_full_abstracts: bool = True
    include_llm_rationale: bool = True
    atomic_writes: bool = True


class RuntimeConfig(BaseModel):
    concurrency: int = Field(default=4, ge=1, le=32)
    per_request_timeout_seconds: int = Field(default=30, ge=5, le=300)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    cache_directory: str = "data/cache"
    cache_ttl_hours: int = Field(default=168, ge=0, le=8760)
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR)$")
    audit_log_path: str = "data/cache/audit.jsonl"


class AppConfig(BaseModel):
    llm: LLMConfig
    # Optional cheap-model screener (two-stage judging). Default: disabled.
    # When omitted from the config file entirely, the screen is off and the
    # pipeline runs in single-stage mode (identical to pre-screener behavior).
    llm_screen: LLMScreenConfig = Field(default_factory=LLMScreenConfig)
    sources: SourcesConfig
    retrieval: RetrievalConfig
    scoring: ScoringConfig
    output: OutputConfig
    runtime: RuntimeConfig

    @model_validator(mode="after")
    def _screen_pool_covers_shortlist(self) -> AppConfig:
        """
        The screener exists to widen the candidate pool, so its pool must be at
        least as large as the detailed judge's shortlist. Inverted, the screen
        silently starves the judge: runner.py takes
        screen_shortlist_size candidates, then slices the survivors to
        llm_shortlist_size, so the judge can never see more than the smaller of
        the two. Only enforced when the screen is on; the field is ignored
        otherwise.
        """
        if self.llm_screen.enabled:
            screen = self.retrieval.screen_shortlist_size
            shortlist = self.retrieval.llm_shortlist_size
            if screen < shortlist:
                raise ValueError(
                    f"retrieval.screen_shortlist_size ({screen}) is smaller than "
                    f"retrieval.llm_shortlist_size ({shortlist}); the screener would "
                    "hand the detailed judge fewer papers than configured. Set the "
                    "screen pool to roughly 2-3x the shortlist, or disable "
                    "llm_screen.enabled."
                )
        return self


def load_config(path: str | Path) -> AppConfig:
    """Load and validate the main config."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping, got {type(data).__name__}")
    return AppConfig.model_validate(data)


def load_taxonomy(path: str | Path) -> Taxonomy:
    """Load and validate the taxonomy."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"taxonomy root must be a mapping, got {type(data).__name__}")
    return Taxonomy.model_validate(data)
