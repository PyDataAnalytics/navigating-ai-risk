"""Tests for scripts/refresh_corpus.py — pure stdlib, no network.

Importable by pytest *and* runnable directly (`python tests/test_refresh_corpus.py`)
so the data-maintenance layer is verifiable without installing the LLM/HTTP deps.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

# Load scripts/refresh_corpus.py as a module without needing it on PYTHONPATH.
_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "refresh_corpus", _ROOT / "scripts" / "refresh_corpus.py"
)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)


def _stats(s2_hit=()):
    return {
        "citations_updated": 0,
        "total_citation_delta": 0,
        "oa_links_added": 0,
        "_s2_hit": set(s2_hit),
    }


def _corpus(papers):
    return {
        "schema_version": "1.0",
        "taxonomy_version": "1.0",
        "corpus_updated_at": "2026-05-30T00:00:00Z",
        "runs": [{"run_id": "r1", "finished_at": "2026-05-30T00:00:00Z"}],
        "taxonomy": [{"category_id": "safety", "category_name": "Safety", "subcategories": ["X"]}],
        "papers": papers,
    }


def _paper(key, doi=None, cites=0, oa=""):
    return {
        "key": key,
        "first_seen": "2026-05-30",
        "last_seen": "2026-05-30",
        "title": key,
        "authors": ["A"],
        "year": 2024,
        "citation_count": cites,
        "doi": doi,
        "arxiv_id": None,
        "semantic_scholar_id": None,
        "oa_pdf_url": oa,
        "placements": [{"category_id": "safety", "subcategory_name": "X"}],
    }


def _s2(cites, oa_url=None):
    pdf = {"url": oa_url} if oa_url else None
    return [{"citationCount": cites, "openAccessPdf": pdf}]


def test_s2_updates_citations_and_backfills_oa():
    papers = [_paper("doi:10.1/a", doi="10.1/a", cites=10, oa="")]
    stats = _stats()

    def post(u, b, h=None):
        return _s2(42, "https://oa.example/a.pdf")

    rc._post = post
    rc.refresh_from_s2(papers, stats)
    assert papers[0]["citation_count"] == 42
    assert papers[0]["oa_pdf_url"] == "https://oa.example/a.pdf"
    assert stats["citations_updated"] == 1
    assert stats["total_citation_delta"] == 32
    assert stats["oa_links_added"] == 1
    assert "doi:10.1/a" in stats["_s2_hit"]


def test_existing_oa_not_overwritten():
    papers = [_paper("doi:10.1/b", doi="10.1/b", cites=5, oa="https://keep.example/b.pdf")]
    stats = _stats()

    def post(u, b, h=None):
        return _s2(5, "https://new.example/b.pdf")

    rc._post = post
    rc.refresh_from_s2(papers, stats)
    assert papers[0]["oa_pdf_url"] == "https://keep.example/b.pdf"  # unchanged
    assert papers[0]["citation_count"] == 5  # unchanged value → not counted
    assert stats["citations_updated"] == 0
    assert stats["oa_links_added"] == 0


def test_failed_batch_leaves_papers_untouched():
    papers = [_paper("doi:10.1/c", doi="10.1/c", cites=7)]
    stats = _stats()

    def post(u, b, h=None):
        return None  # whole batch failed

    rc._post = post
    rc.refresh_from_s2(papers, stats)
    assert papers[0]["citation_count"] == 7
    assert stats["citations_updated"] == 0


def test_openalex_only_hits_unresolved_papers():
    resolved = _paper("doi:10.1/d", doi="10.1/d", cites=1)
    missed = _paper("doi:10.1/e", doi="10.1/e", cites=1)
    papers = [resolved, missed]
    stats = _stats(s2_hit=["doi:10.1/d"])
    hit = {"ids": {"doi": "https://doi.org/10.1/e"}, "cited_by_count": 99, "open_access": {}}

    def get(u, h=None):
        return {"results": [hit]}

    rc._get = get
    rc.refresh_from_openalex(papers, stats)
    assert resolved["citation_count"] == 1  # S2 already resolved it → skipped
    assert missed["citation_count"] == 99  # OpenAlex picked up the gap


def test_validate_catches_first_seen_mutation():
    corpus = _corpus([_paper("k1", cites=1)])
    corpus["papers"][0]["first_seen"] = "2026-06-01"  # illegal mutation
    errs = rc.validate(corpus, prev_count=1, prev_first_seen={"k1": "2026-05-30"})
    assert any("first_seen mutated" in e for e in errs)


def test_validate_catches_count_change_and_abstract_leak():
    leak = {"key": "k2", "first_seen": "2026-05-30", "abstract": "leak"}
    corpus = _corpus([_paper("k1"), leak])
    errs = rc.validate(corpus, prev_count=1, prev_first_seen={"k1": "2026-05-30"})
    assert any("paper count changed" in e for e in errs)
    assert any("abstract leaked" in e for e in errs)


def test_end_to_end_main_writes_valid_corpus():
    papers = [_paper("doi:10.1/z", doi="10.1/z", cites=3, oa="")]
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "corpus.json"
        path.write_text(json.dumps(_corpus(papers)), encoding="utf-8")

        def post(u, b, h=None):
            return _s2(50, "https://oa.example/z.pdf")

        def get(u, h=None):
            return {"results": []}

        rc._post = post
        rc._get = get
        argv = sys.argv
        sys.argv = ["refresh_corpus.py", "--corpus", str(path)]
        try:
            assert rc.main() == 0
        finally:
            sys.argv = argv
        out = json.loads(path.read_text(encoding="utf-8"))
        p = out["papers"][0]
        assert p["citation_count"] == 50
        assert p["oa_pdf_url"] == "https://oa.example/z.pdf"
        assert p["first_seen"] == "2026-05-30"  # immutable
        assert "last_refreshed" in p
        assert len(out["refreshes"]) == 1
        assert out["refreshes"][0]["citations_updated"] == 1
        assert out["last_refreshed_at"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
