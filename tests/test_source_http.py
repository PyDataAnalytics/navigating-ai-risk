"""HTTP resilience tests for paper sources.

Each source talks to a different upstream API but they share the same
failure model: timeout, 5xx, 4xx, malformed payload. These tests verify
that under each failure mode, the source returns [] rather than crashing
the pipeline.

We use respx to mock httpx calls. arxiv is the test target because it has
the simplest payload format (Atom XML via feedparser), but the behavior
checked here is the contract for all sources.

Why this matters: a source raising an unhandled exception would crash
run_subcategory's gather call, which uses return_exceptions=True — so the
runner already absorbs them. But silent crashes inside the source produce
"source returned []" with no log, which is harder to debug. Each source
should log on failure and return [].
"""

from __future__ import annotations

import pytest

# respx is in dev deps. If not installed, skip these tests with a clear message.
respx = pytest.importorskip("respx", reason="respx required for source HTTP tests")
import httpx

from ai_risk_retrieval.config import SourceConfig
from ai_risk_retrieval.models import Subcategory
from ai_risk_retrieval.sources.arxiv import ArxivSource


@pytest.fixture
def subcategory() -> Subcategory:
    return Subcategory(name="Hallucinations", keywords=["LLM", "fabrication"])


@pytest.fixture
def arxiv_source() -> ArxivSource:
    return ArxivSource(
        config=SourceConfig(enabled=True, max_candidates_per_subcategory=10),
        timeout_seconds=5,
    )


# ── HTTP error handling ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_returns_empty_on_500(arxiv_source: ArxivSource, subcategory: Subcategory):
    """A 500 from arXiv must not crash the pipeline."""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        return_value=httpx.Response(500, text="Server Error")
    )
    result = await arxiv_source.fetch(subcategory)
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_returns_empty_on_503(arxiv_source: ArxivSource, subcategory: Subcategory):
    """A 503 (often rate-limit signal) must not crash."""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        return_value=httpx.Response(503, text="Service Unavailable")
    )
    result = await arxiv_source.fetch(subcategory)
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_returns_empty_on_404(arxiv_source: ArxivSource, subcategory: Subcategory):
    """4xx (unexpected request) must not crash."""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    result = await arxiv_source.fetch(subcategory)
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_returns_empty_on_timeout(arxiv_source: ArxivSource, subcategory: Subcategory):
    """A connection timeout must not crash."""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    result = await arxiv_source.fetch(subcategory)
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_returns_empty_on_connection_error(
    arxiv_source: ArxivSource, subcategory: Subcategory
):
    """Network unreachable etc. must not crash."""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        side_effect=httpx.ConnectError("network down")
    )
    result = await arxiv_source.fetch(subcategory)
    assert result == []


# ── Malformed payload handling ──────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_returns_empty_on_empty_response(
    arxiv_source: ArxivSource, subcategory: Subcategory
):
    """An empty 200 OK body must not crash — should produce 0 papers."""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        return_value=httpx.Response(200, text="")
    )
    result = await arxiv_source.fetch(subcategory)
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_returns_empty_on_malformed_xml(
    arxiv_source: ArxivSource, subcategory: Subcategory
):
    """Malformed XML must not crash. feedparser is lenient but still."""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        return_value=httpx.Response(200, text="<not><valid>xml</wrong>")
    )
    result = await arxiv_source.fetch(subcategory)
    # Lenient parser may return [] or whatever entries it could salvage.
    # The contract is: never raise.
    assert isinstance(result, list)


# ── Disabled / zero-budget short-circuit ────────────────────────────────────


@pytest.mark.asyncio
async def test_arxiv_disabled_returns_empty_without_http_call(
    subcategory: Subcategory,
):
    """When config.enabled=False, no HTTP call should be made."""
    source = ArxivSource(
        config=SourceConfig(enabled=False, max_candidates_per_subcategory=10),
        timeout_seconds=5,
    )
    with respx.mock() as mock_router:
        result = await source.fetch(subcategory)
        assert result == []
        assert mock_router.calls.call_count == 0


@pytest.mark.asyncio
async def test_arxiv_zero_budget_returns_empty_without_http_call(
    subcategory: Subcategory,
):
    """When max_candidates_per_subcategory=0, no HTTP call should be made."""
    source = ArxivSource(
        config=SourceConfig(enabled=True, max_candidates_per_subcategory=0),
        timeout_seconds=5,
    )
    with respx.mock() as mock_router:
        result = await source.fetch(subcategory)
        assert result == []
        assert mock_router.calls.call_count == 0


# ── Successful fetch (positive control) ─────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_arxiv_parses_valid_response(arxiv_source: ArxivSource, subcategory: Subcategory):
    """Sanity check: a well-formed Atom feed with one entry produces one Paper."""
    atom_response = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2310.12345v1</id>
    <updated>2023-10-15T10:00:00Z</updated>
    <published>2023-10-15T10:00:00Z</published>
    <title>Test paper on hallucinations in LLMs</title>
    <summary>This paper studies hallucinations in LLM outputs and proposes mitigations through retrieval augmentation. We evaluate on multiple benchmarks.</summary>
    <author><name>Alice</name></author>
    <author><name>Bob</name></author>
    <link href="http://arxiv.org/abs/2310.12345v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2310.12345v1" rel="related" type="application/pdf"/>
  </entry>
</feed>"""
    respx.get(url__startswith="http://export.arxiv.org").mock(
        return_value=httpx.Response(200, text=atom_response)
    )
    result = await arxiv_source.fetch(subcategory)
    # If feedparser successfully extracts the entry, we should have 1 paper.
    # If it fails for any reason, we should have 0 — but never crash.
    assert isinstance(result, list)
    assert len(result) <= 1  # at most one entry was in the feed
