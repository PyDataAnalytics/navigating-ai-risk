"""
Output writer. Writes JSON atomically so a webapp polling the file never
sees a half-written document.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import structlog

from ..config import OutputConfig
from ..models import RetrievalRun

log = structlog.get_logger()


def write_run(run: RetrievalRun, config: OutputConfig) -> Path:
    """Write a RetrievalRun to disk. Returns the path written."""
    out_dir = Path(config.directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Two files: a timestamped historical record and a `latest.json` pointer.
    ts = run.started_at.strftime("%Y%m%dT%H%M%SZ")
    primary_path = out_dir / f"results-{ts}.json"
    latest_path = out_dir / "latest.json"

    # Reshape for output: optionally drop verbose fields per config
    data = run.model_dump(mode="json")
    if not config.include_full_abstracts:
        for r in data["results"]:
            for sp in r["selected_papers"]:
                sp["paper"]["abstract"] = sp["paper"]["abstract"][:300] + "…"
    if not config.include_llm_rationale:
        for r in data["results"]:
            for sp in r["selected_papers"]:
                sp["llm"].pop("rationale", None)

    payload = json.dumps(data, indent=2, ensure_ascii=False, default=str)

    if config.atomic_writes:
        _atomic_write(primary_path, payload)
        _atomic_write(latest_path, payload)
    else:
        primary_path.write_text(payload, encoding="utf-8")
        latest_path.write_text(payload, encoding="utf-8")

    log.info("results_written", path=str(primary_path), bytes=len(payload))
    return primary_path


def _atomic_write(path: Path, content: str) -> None:
    """Write to a tempfile in the same directory, then rename."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        # Clean up tempfile on failure
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
