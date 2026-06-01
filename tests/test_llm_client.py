"""Tests for the Ollama LLM client.

Exercises config validation, client construction, and the full chat() request
shape against a fake Ollama async client (the `ollama` package must be
importable - it's a project dependency, but no Ollama server is needed).

Run from the project root:
    pytest tests/test_llm_client.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the package importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ai_risk_retrieval.config import LLMConfig, LLMScreenConfig
from ai_risk_retrieval.evaluator.llm_client import LLMClient


# ---- Config validation -----------------------------------------------------
class TestConfigValidation:
    """Config-level guardrails: bad configs must fail at load time, not later."""

    def test_ollama_accepts_localhost(self):
        cfg = LLMConfig(
            provider="ollama",
            host="http://127.0.0.1:11434",
            model="llama3.1:8b",
        )
        assert cfg.provider == "ollama"

    def test_ollama_rejects_remote_host(self):
        with pytest.raises(Exception, match="is not local"):
            LLMConfig(
                provider="ollama",
                host="http://some.remote.host:11434",
                model="llama3.1:8b",
            )

    def test_openai_compatible_now_rejected(self):
        """The hosted-API path was removed; only 'ollama' is allowed."""
        with pytest.raises(Exception, match="ollama"):
            LLMConfig(
                provider="openai_compatible",
                host="https://api.groq.com/openai/v1",
                model="llama-3.1-8b-instant",
            )

    def test_unknown_provider_rejected(self):
        with pytest.raises(Exception, match="ollama"):
            LLMConfig(
                provider="claude_native",
                host="https://api.anthropic.com",
                model="claude-3-haiku",
            )

    def test_screen_config_rejects_non_ollama(self):
        with pytest.raises(Exception, match="ollama"):
            LLMScreenConfig(
                enabled=True,
                provider="openai_compatible",
                host="https://api.groq.com/openai/v1",
                model="llama-3.1-8b-instant",
            )

    def test_screen_config_rejects_remote_host(self):
        with pytest.raises(Exception, match="is not local"):
            LLMScreenConfig(
                enabled=True,
                provider="ollama",
                host="http://some.remote.host:11434",
                model="llama3.2:3b",
            )


# ---- Client construction ---------------------------------------------------
class TestClientConstruction:
    def test_ollama_constructs(self):
        cfg = LLMConfig(
            provider="ollama",
            host="http://127.0.0.1:11434",
            model="llama3.1:8b",
        )
        client = LLMClient(cfg)
        assert client.provider == "ollama"
        assert client._ollama_client is not None


# ---- chat() ----------------------------------------------------------------
class _FakeOllama:
    """Stand-in for ollama.AsyncClient: records calls, returns a canned reply."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def _client_with_fake(response):
    cfg = LLMConfig(provider="ollama", host="http://127.0.0.1:11434", model="m")
    client = LLMClient(cfg)
    client._ollama_client = _FakeOllama(response)
    return client, client._ollama_client


@pytest.mark.asyncio
async def test_ollama_chat_request_and_response():
    """The outgoing kwargs and the normalized return shape are both correct."""
    client, fake = _client_with_fake({"message": {"content": '{"relevance": 8}'}})
    result = await client.chat(
        model="llama3.1:8b",
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
        ],
        json_mode=True,
        temperature=0.0,
        num_ctx=4096,
    )
    sent = fake.calls[-1]
    assert sent["model"] == "llama3.1:8b"
    assert sent["format"] == "json"
    assert sent["options"]["temperature"] == 0.0
    assert sent["options"]["num_ctx"] == 4096
    assert sent["messages"][0] == {"role": "system", "content": "sys"}
    assert result["message"]["content"] == '{"relevance": 8}'
    await client.aclose()


@pytest.mark.asyncio
async def test_ollama_chat_no_json_mode():
    """json_mode=False must not set format=json."""
    client, fake = _client_with_fake({"message": {"content": "hi"}})
    await client.chat(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        json_mode=False,
    )
    assert "format" not in fake.calls[-1]
    await client.aclose()


@pytest.mark.asyncio
async def test_ollama_chat_normalizes_object_with_model_dump():
    """Newer Ollama returns an object; model_dump() is used to normalize it."""

    class _Resp:
        def model_dump(self):
            return {"message": {"content": "ok"}}

    client, _ = _client_with_fake(_Resp())
    result = await client.chat(model="m", messages=[{"role": "user", "content": "x"}])
    assert result["message"]["content"] == "ok"
    await client.aclose()


@pytest.mark.asyncio
async def test_ollama_chat_normalizes_unexpected_response():
    """A non-dict response degrades gracefully to empty content."""
    client, _ = _client_with_fake("not a dict")
    result = await client.chat(model="m", messages=[{"role": "user", "content": "x"}])
    assert result == {"message": {"content": ""}}
    await client.aclose()
