"""Tests for storage/writer.py.

The writer is the last hop before output reaches the webapp. Failures here
mean either silent data loss or a half-written file the downstream consumer
will choke on. We test atomicity, schema preservation, and the
include_full_abstracts / include_llm_rationale flags.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ai_risk_retrieval.config import OutputConfig
from ai_risk_retrieval.models import (
    LLMJudgement,
    Paper,
    RetrievalRun,
    ScoredPaper,
    SubcategoryResult,
)
from ai_risk_retrieval.storage.writer import write_run


def _make_paper(title: str = "Test paper") -> Paper:
    return Paper(
        title=title,
        abstract="A" * 500,  # long abstract to test truncation logic
        authors=["Alice", "Bob"],
        year=2024,
        url="https://example.com/paper",
        source="arxiv",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        content_hash="a" * 64,
    )


def _make_run() -> RetrievalRun:
    paper = _make_paper()
    judgement = LLMJudgement(relevance=8.0, rationale="Strong direct relevance to topic.")
    scored = ScoredPaper(paper=paper, llm=judgement, composite_score=7.5)
    result = SubcategoryResult(
        category_id="technical",
        category_name="Technical Risks",
        subcategory_name="Hallucinations",
        selected_papers=[scored],
        candidate_count=42,
        shortlist_count=20,
        generated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    return RetrievalRun(
        run_id="test-run-1",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        finished_at=datetime(2024, 1, 1, 1, tzinfo=UTC),
        taxonomy_version="2.2",
        llm_model="llama3.1:8b",
        results=[result],
    )


# ── Basic writes ─────────────────────────────────────────────────────────────


def test_write_creates_timestamped_and_latest(tmp_path: Path):
    """Both a results-<ts>.json AND a latest.json should appear."""
    config = OutputConfig(
        directory=str(tmp_path),
        include_full_abstracts=True,
        include_llm_rationale=True,
        atomic_writes=True,
    )
    run = _make_run()
    primary = write_run(run, config)
    assert primary.exists()
    assert primary.name.startswith("results-")
    assert primary.suffix == ".json"
    assert (tmp_path / "latest.json").exists()


def test_written_json_is_parseable_and_matches_schema(tmp_path: Path):
    """Round-trip: write then read; must equal the source RetrievalRun."""
    config = OutputConfig(
        directory=str(tmp_path),
        include_full_abstracts=True,
        include_llm_rationale=True,
        atomic_writes=False,
    )
    run = _make_run()
    primary = write_run(run, config)
    data = json.loads(primary.read_text(encoding="utf-8"))
    assert data["run_id"] == "test-run-1"
    assert data["taxonomy_version"] == "2.2"
    assert len(data["results"]) == 1
    assert data["results"][0]["subcategory_name"] == "Hallucinations"
    assert len(data["results"][0]["selected_papers"]) == 1
    # Reverse-parse with Pydantic to confirm strict schema compliance
    reparsed = RetrievalRun.model_validate(data)
    assert reparsed.run_id == run.run_id


# ── Field-stripping flags ────────────────────────────────────────────────────


def test_drops_full_abstracts_when_flag_false(tmp_path: Path):
    config = OutputConfig(
        directory=str(tmp_path),
        include_full_abstracts=False,
        include_llm_rationale=True,
        atomic_writes=False,
    )
    run = _make_run()
    primary = write_run(run, config)
    data = json.loads(primary.read_text(encoding="utf-8"))
    abstract = data["results"][0]["selected_papers"][0]["paper"]["abstract"]
    # Should be truncated to ~300 + ellipsis
    assert len(abstract) < 500
    assert abstract.endswith("…")


def test_keeps_full_abstracts_when_flag_true(tmp_path: Path):
    config = OutputConfig(
        directory=str(tmp_path),
        include_full_abstracts=True,
        include_llm_rationale=True,
        atomic_writes=False,
    )
    run = _make_run()
    primary = write_run(run, config)
    data = json.loads(primary.read_text(encoding="utf-8"))
    abstract = data["results"][0]["selected_papers"][0]["paper"]["abstract"]
    assert len(abstract) == 500
    assert not abstract.endswith("…")


def test_drops_rationale_when_flag_false(tmp_path: Path):
    config = OutputConfig(
        directory=str(tmp_path),
        include_full_abstracts=True,
        include_llm_rationale=False,
        atomic_writes=False,
    )
    run = _make_run()
    primary = write_run(run, config)
    data = json.loads(primary.read_text(encoding="utf-8"))
    llm = data["results"][0]["selected_papers"][0]["llm"]
    assert "rationale" not in llm
    # Score must still be present
    assert "relevance" in llm


# ── Atomicity ────────────────────────────────────────────────────────────────


def test_atomic_writes_leave_no_tempfiles(tmp_path: Path):
    """After atomic_writes, no .tmp files should remain in the output dir."""
    config = OutputConfig(
        directory=str(tmp_path),
        include_full_abstracts=True,
        include_llm_rationale=True,
        atomic_writes=True,
    )
    run = _make_run()
    write_run(run, config)
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Stale tempfiles remain: {tmp_files}"
    dotfiles = list(tmp_path.glob(".*.tmp"))
    assert dotfiles == [], f"Stale dot-tempfiles remain: {dotfiles}"


def test_atomic_writes_creates_target_only_after_full_write(tmp_path: Path):
    """The target file's existence implies a complete write — never a partial one.

    We can't easily simulate a crash mid-write here without OS-level tooling,
    but we can verify that after a successful write the file is parseable JSON.
    """
    config = OutputConfig(
        directory=str(tmp_path),
        include_full_abstracts=True,
        include_llm_rationale=True,
        atomic_writes=True,
    )
    run = _make_run()
    primary = write_run(run, config)
    # If atomic_writes worked, the file must be fully parseable
    json.loads(primary.read_text(encoding="utf-8"))


# ── Output stability (reproducibility) ───────────────────────────────────────


def test_two_writes_of_same_run_produce_identical_content(tmp_path: Path):
    """Writing the same RetrievalRun twice should produce byte-identical JSON.

    Important for production: an unchanged input must produce an unchanged
    output, or downstream cache invalidation triggers spuriously.
    """
    config1 = OutputConfig(
        directory=str(tmp_path / "a"),
        atomic_writes=False,
        include_full_abstracts=True,
        include_llm_rationale=True,
    )
    config2 = OutputConfig(
        directory=str(tmp_path / "b"),
        atomic_writes=False,
        include_full_abstracts=True,
        include_llm_rationale=True,
    )
    run = _make_run()
    p1 = write_run(run, config1)
    p2 = write_run(run, config2)
    assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")


# ── Directory creation ───────────────────────────────────────────────────────


def test_creates_nested_output_directory(tmp_path: Path):
    nested = tmp_path / "deeply" / "nested" / "output"
    config = OutputConfig(
        directory=str(nested),
        include_full_abstracts=True,
        include_llm_rationale=True,
        atomic_writes=False,
    )
    run = _make_run()
    primary = write_run(run, config)
    assert primary.exists()
    assert primary.parent == nested
