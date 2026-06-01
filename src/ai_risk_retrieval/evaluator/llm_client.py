"""LLM client for self-hosted Ollama.

This is the seam where the retriever talks to an LLM. The rest of the
pipeline (judge, screener, query_expander) never touches Ollama or HTTP
directly - they all call `LLMClient.chat()` and get back the same dict shape.

Every LLM step in this project runs on a self-hosted Ollama instance. There
is no remote/hosted-API provider: no paper content or derived analysis is
ever sent to a third-party LLM service.

Security posture:
  - Ollama host is localhost-only (validated at config load).
  - Same prompt sanitization and audit logging upstream.
  - Same strict JSON response parsing downstream.
"""

from __future__ import annotations

import asyncio
from typing import Any

try:
    import ollama
except ImportError:  # pragma: no cover
    ollama = None  # type: ignore


class LLMClientError(Exception):
    """Raised when the client is misconfigured (not when the API call fails)."""


class LLMClient:
    """Ollama-backed LLM client.

    `chat()` is the single call surface; downstream code reads
    `response["message"]["content"]` and nothing else.
    """

    def __init__(self, config: Any) -> None:
        """
        Args:
            config: An LLMConfig or LLMScreenConfig (anything with provider,
                    host, model, request_timeout_seconds). Accepting `Any`
                    here lets us share one client across both.
        """
        self.config = config
        self.provider = getattr(config, "provider", "ollama")
        if self.provider != "ollama":
            raise LLMClientError(
                f"Unknown LLM provider: {self.provider!r}. Only 'ollama' is supported."
            )
        if ollama is None:
            raise LLMClientError(
                "provider=ollama requires the 'ollama' Python package. "
                "Install with: pip install ollama"
            )
        self._ollama_client = ollama.AsyncClient(host=config.host)

    async def aclose(self) -> None:
        """No-op; kept so callers can uniformly `await client.aclose()`."""
        return None

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        json_mode: bool = True,
        temperature: float = 0.0,
        num_ctx: int | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request to Ollama.

        Output shape:
            {"message": {"content": "<text from the model>"}}

        Args:
            model:       Ollama model name, e.g. "llama3.1:8b".
            messages:    List of {role, content} dicts.
            json_mode:   Force JSON output (Ollama format="json").
            temperature: Sampling temperature 0.0-1.0.
            num_ctx:     Ollama context window.

        Raises:
            asyncio.TimeoutError: request exceeded request_timeout_seconds.
            Exception:            any other Ollama error. Caller catches/logs.
        """
        options: dict[str, Any] = {"temperature": temperature}
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "options": options,
        }
        if json_mode:
            kwargs["format"] = "json"
        result = await asyncio.wait_for(
            self._ollama_client.chat(**kwargs),
            timeout=self.config.request_timeout_seconds,
        )
        # Ollama returns either a dict or an object depending on version;
        # normalize to dict.
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        return result if isinstance(result, dict) else {"message": {"content": ""}}
