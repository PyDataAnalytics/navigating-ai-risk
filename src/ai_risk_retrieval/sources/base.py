"""
Base class and shared helpers for paper sources.

Every source returns a list of `Paper` objects. The base class handles:
- query construction from a Subcategory
- content hashing
- a uniform interface for the pipeline
- shared HTTP client config (timeouts, retries, user-agent)
"""

from __future__ import annotations

import abc
import hashlib
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import SourceConfig
from ..models import Paper, Subcategory

log = structlog.get_logger()

# A polite, identifying UA. Many academic APIs request this.
USER_AGENT = "ai-risk-retrieval/0.1 (research)"


class PaperSource(abc.ABC):
    """Abstract source adapter. Subclass and implement `fetch`."""

    name: str  # set by subclasses; matches SourceName literal

    def __init__(self, config: SourceConfig, timeout_seconds: int = 30) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    async def fetch(self, subcategory: Subcategory) -> list[Paper]:
        """Return candidate papers for one subcategory. Bounded by config."""

    # ── shared helpers ──────────────────────────────────────────────────────

    def build_query(self, subcategory: Subcategory) -> str:
        """Default query: subcategory name plus optional keywords, OR-joined."""
        terms = [subcategory.name, *subcategory.keywords]
        # Quote multi-word terms so APIs treat them as phrases when supported
        quoted = [f'"{t}"' if " " in t else t for t in terms]
        return " OR ".join(quoted)

    @staticmethod
    def content_hash(*parts: str) -> str:
        """Stable SHA-256 over the canonical content fields."""
        h = hashlib.sha256()
        for p in parts:
            h.update(p.encode("utf-8", errors="replace"))
            h.update(b"\x00")
        return h.hexdigest()

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )


# Decorator for transient-error retries. Sources opt in.
retryable = retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)


def safe_text(value: Any, max_len: int = 10_000) -> str:
    """Coerce arbitrary API field to bounded plain text."""
    if value is None:
        return ""
    s = str(value)
    # Strip C0 control characters except tab/newline. These often appear in
    # bad scrapes and can break downstream tooling.
    cleaned = "".join(
        c for c in s if c == "\t" or c == "\n" or 0x20 <= ord(c) < 0x7F or ord(c) >= 0xA0
    )
    return cleaned[:max_len]
