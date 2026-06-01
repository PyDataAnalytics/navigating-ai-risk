"""
LLM-driven query expansion.

The naive query `subcategory.name OR keyword1 OR keyword2` undersamples
sparse subcategories (e.g. "Wireheading", "Reality apathy") and produces
broad noise for dense ones. We use the LLM — once per subcategory, cached
forever — to generate 3-6 strong search queries: synonyms, related technical
terms, and concrete examples.

The cost is bounded and amortized: ~150 calls per *taxonomy version*, not
per run. Re-running the pipeline with the same taxonomy uses the cache and
makes zero expansion calls.

Security model
--------------
Subcategories come from a taxonomy file the operator controls, not from the
open web, so the prompt-injection threat is much lower than for paper text.
We still:
- run the subcategory through the same sanitizer (defense in depth, cheap),
- force `format=json` and validate the LLM response with Pydantic,
- treat any expansion output as a list of bounded strings only — never
  templated back into instructions.

If the LLM call fails or returns malformed output, we fall back to the
original keyword list. Expansion is an optimization, never a dependency.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field, ValidationError

try:
    import ollama
except ImportError:  # pragma: no cover
    ollama = None  # type: ignore

from ..config import LLMConfig
from ..models import Subcategory
from .llm_client import LLMClient
from .sanitizer import sanitize_paper_text

log = structlog.get_logger()


# ─── Schemas ────────────────────────────────────────────────────────────────


class ExpansionResult(BaseModel):
    """Validated LLM output: a small list of bounded query strings."""

    queries: list[str] = Field(min_length=1, max_length=8)

    @classmethod
    def from_raw(cls, raw_queries: list[Any]) -> ExpansionResult:
        # Coerce each item to a string and apply length + character limits.
        # Anything that doesn't look like a search query is dropped.
        cleaned: list[str] = []
        for q in raw_queries:
            if not isinstance(q, str):
                continue
            # Strip control chars and HTML-ish tokens; cap length
            q = re.sub(r"[\x00-\x1f<>]", " ", q).strip()
            q = re.sub(r"\s+", " ", q)
            if 3 <= len(q) <= 200:
                cleaned.append(q)
        # Dedup while preserving order
        seen: set[str] = set()
        unique = []
        for q in cleaned:
            key = q.lower()
            if key not in seen:
                seen.add(key)
                unique.append(q)
        return cls(queries=unique[:6])


# ─── Prompt ─────────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """\
You generate search queries for an academic paper retrieval system focused \
on AI risk research. Given an AI risk subcategory name, return a JSON object \
with 4-6 short, diverse search queries that would surface the most relevant \
academic papers from arXiv, Semantic Scholar, OpenAlex, and similar sources.

Each query should be a phrase a researcher would actually type into a paper \
search tool. Mix:
- the exact term and obvious synonyms,
- adjacent technical terminology used in the literature,
- one or two concrete examples or mechanisms.

Avoid:
- queries longer than 8 words,
- vague single-word queries,
- boolean syntax (AND/OR/NOT) — the retrieval layer handles that,
- generic terms like "AI" or "machine learning" alone.

Output schema (return ONLY this JSON object, nothing else):
{
  "queries": ["query 1", "query 2", "query 3", "query 4"]
}"""


USER_TEMPLATE = """\
AI risk subcategory: {name}
Operator hints (may be empty): {keywords}

Return JSON only."""


# ─── Expander ───────────────────────────────────────────────────────────────


class QueryExpander:
    """Generates and caches expanded query lists per subcategory."""

    def __init__(
        self,
        config: LLMConfig,
        cache_path: str | Path,
        taxonomy_version: str,
    ) -> None:
        self.config = config
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.taxonomy_version = taxonomy_version
        # Build the LLM client. If construction fails (e.g. missing API key),
        # we log and continue without expansion — graceful degradation, the
        # rest of the pipeline works with base keywords.
        try:
            self._client: LLMClient | None = LLMClient(config)
        except Exception as e:
            log.warning("query_expander_disabled", reason=str(e))
            self._client = None
        self._cache: dict[str, list[str]] = self._load_cache()
        self._lock = asyncio.Lock()  # protects cache file writes

    # Public API ─────────────────────────────────────────────────────────────

    async def expand(self, subcategory: Subcategory) -> list[str]:
        """
        Return a list of search query strings for this subcategory.

        Always includes the subcategory name itself plus the operator's
        manual keywords; appends LLM-generated expansions when available.
        Returns at minimum [subcategory.name] so callers can always rely
        on a non-empty result.
        """
        base = [subcategory.name, *subcategory.keywords]
        cache_key = self._cache_key(subcategory)

        if cache_key in self._cache:
            return self._merge_unique(base + self._cache[cache_key])

        # Cache miss — call the LLM
        generated = await self._call_llm(subcategory)
        if generated:
            self._cache[cache_key] = generated
            await self._persist_cache()
        # If generation failed, fall back to base queries only
        return self._merge_unique(base + generated)

    # Internals ──────────────────────────────────────────────────────────────

    def _cache_key(self, subcategory: Subcategory) -> str:
        """
        Stable hash over taxonomy version + model + subcategory name.

        Including the model means swapping models invalidates the cache,
        which is correct: different models produce different expansions.
        """
        material = f"{self.taxonomy_version}|{self.config.model}|{subcategory.name}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def _load_cache(self) -> dict[str, list[str]]:
        if not self.cache_path.exists():
            return {}
        try:
            with self.cache_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return {}
            # Coerce each value into a list of strings for safety
            out: dict[str, list[str]] = {}
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, list):
                    out[k] = [s for s in v if isinstance(s, str)]
            return out
        except (OSError, json.JSONDecodeError) as e:
            log.warning("query_cache_load_failed", error=str(e))
            return {}

    async def _persist_cache(self) -> None:
        """Write the cache atomically. Holds a lock to serialize writes."""
        async with self._lock:
            try:
                payload = json.dumps(self._cache, indent=2, ensure_ascii=False)
                fd, tmp = tempfile.mkstemp(
                    dir=str(self.cache_path.parent),
                    prefix=f".{self.cache_path.name}.",
                    suffix=".tmp",
                )
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, self.cache_path)
            except OSError as e:
                log.warning("query_cache_write_failed", error=str(e))

    async def _call_llm(self, subcategory: Subcategory) -> list[str]:
        """Generate expansions. Returns [] on any failure."""
        if self._client is None:
            log.debug("query_expansion_skipped", reason="llm client unavailable")
            return []

        # Same sanitizer as for paper text — defense in depth even though
        # subcategories come from a trusted file.
        name_clean = sanitize_paper_text(subcategory.name, max_chars=200)
        keywords_clean = sanitize_paper_text(
            ", ".join(subcategory.keywords) if subcategory.keywords else "(none)",
            max_chars=500,
        )
        user_msg = USER_TEMPLATE.format(name=name_clean, keywords=keywords_clean)

        try:
            response = await self._client.chat(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                json_mode=True,
                temperature=0.3,  # a little variety in expansions
                num_ctx=self.config.num_ctx,
            )
        except TimeoutError:
            log.warning("query_expansion_timeout", subcategory=subcategory.name)
            return []
        except Exception as e:
            log.warning("query_expansion_failed", subcategory=subcategory.name, error=str(e))
            return []

        raw = (
            (response.get("message") or {}).get("content", "") if isinstance(response, dict) else ""
        )
        return self._parse(raw, subcategory.name)

    @staticmethod
    def _parse(raw: str, subcategory_name: str) -> list[str]:
        """Strict parse. Anything off-spec → empty list (graceful fallback)."""
        if not raw:
            return []
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            data = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            log.debug("expansion_json_invalid", subcategory=subcategory_name)
            return []
        if not isinstance(data, dict):
            return []
        queries_raw = data.get("queries")
        if not isinstance(queries_raw, list):
            return []
        try:
            return ExpansionResult.from_raw(queries_raw).queries
        except ValidationError:
            return []

    @staticmethod
    def _merge_unique(items: list[str]) -> list[str]:
        """Order-preserving unique."""
        seen: set[str] = set()
        out: list[str] = []
        for q in items:
            if not q:
                continue
            key = q.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(q.strip())
        return out
