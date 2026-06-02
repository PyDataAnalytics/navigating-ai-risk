#!/usr/bin/env python3
"""
refresh_corpus.py — weekly, GPU-free maintenance of the durable corpus.

This is the *incremental* half of the pipeline. The expensive *discovery* half
(LLM query-expansion + screen + judge) finds brand-new papers and must run on a
GPU (Ollama is local-only) — see `.github/workflows/discovery.yml`. THIS script
runs every week on a free CPU runner and keeps the existing corpus alive:

  • citation counts        — re-pulled from Semantic Scholar (batch) + OpenAlex
  • open-access PDF links   — backfilled from Semantic Scholar + Unpaywall
  • a `last_refreshed` clock — added per paper, alongside the immutable first_seen
  • a `refreshes` history    — one append-only record per run, so the corpus
                               itself remembers how it has changed over time

Design goals (mirrors merge_corpus.py):
  - **stdlib only**  — no pip install in CI; nothing to break a scheduled run.
  - **best-effort**  — any single HTTP failure is swallowed; a run never aborts
                       and never partially corrupts the corpus.
  - **safe**         — validate-before-write (paper count constant, first_seen
                       never mutated, no abstract leak, JSON round-trips) then
                       atomic replace.
  - **idempotent**   — re-running on the same day is a no-op-ish refresh; it
                       never duplicates papers or rewrites first_seen.
  - **performant**   — batched requests (1 S2 call / 50-DOI OpenAlex pages)
                       instead of one request per paper; the whole 323-paper
                       corpus refreshes in seconds.

Credentials (all optional — the script degrades gracefully):
  SEMANTIC_SCHOLAR_API_KEY  lifts the S2 rate limit (sent as x-api-key header)
  OPENALEX_MAILTO           enters OpenAlex's faster "polite pool"
  UNPAYWALL_EMAIL           enables Unpaywall OA backfill (the API needs a contact)

With NO credentials set the script still refreshes citations via the key-less
S2/OpenAlex paths; it only skips the Unpaywall OA backfill.

Copyright: we read and store *metadata only* (citation counts, OA link URLs).
We never fetch or republish full text — exactly the corpus's existing stance.

Usage:
  python scripts/refresh_corpus.py --corpus corpus.json
  python scripts/refresh_corpus.py --corpus corpus.json --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
OPENALEX_URL = "https://api.openalex.org/works"
UNPAYWALL_URL = "https://api.unpaywall.org/v2"
USER_AGENT = "ai-risk-retrieval/0.1 (corpus refresh; metadata only)"

S2_BATCH_SIZE = 500  # S2 batch endpoint accepts up to 500 ids per request
OA_PAGE_SIZE = 50  # OpenAlex OR-filter page size
HTTP_TIMEOUT = 30.0


# --------------------------------------------------------------------------- #
# tiny stdlib HTTP helpers (best-effort; callers handle None)
# --------------------------------------------------------------------------- #
def _http(req: Request) -> dict | list | None:
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as r:  # noqa: S310 (https only, fixed hosts)
            return json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        if e.code not in (404,):  # 404 is a normal "not found", stay quiet
            print(f"  http {e.code}: {req.full_url[:90]}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001 — best-effort: any failure is a quiet miss
        print(f"  {type(e).__name__}: {req.full_url[:90]}", file=sys.stderr)
        return None


def _get(url: str, headers: dict | None = None) -> dict | list | None:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    h.update(headers or {})
    return _http(Request(url, headers=h))


def _post(url: str, body: dict, headers: dict | None = None) -> dict | list | None:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    h.update(headers or {})
    data = json.dumps(body).encode("utf-8")
    return _http(Request(url, data=data, headers=h, method="POST"))


# --------------------------------------------------------------------------- #
# identifier helpers
# --------------------------------------------------------------------------- #
def s2_query_id(entry: dict) -> str | None:
    """Best Semantic Scholar lookup id for a corpus paper (DOI > arXiv > S2 id)."""
    if doi := entry.get("doi"):
        return f"DOI:{doi}"
    if ax := entry.get("arxiv_id"):
        return f"ARXIV:{ax}"
    if s2 := entry.get("semantic_scholar_id"):
        return str(s2)
    return None


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _valid_citation(value) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _oa_url(open_access_pdf) -> str | None:
    if isinstance(open_access_pdf, dict):
        url = open_access_pdf.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
    return None


# --------------------------------------------------------------------------- #
# source refreshers — each mutates `entry` dicts in place, returns counts
# --------------------------------------------------------------------------- #
def refresh_from_s2(papers: list[dict], stats: dict) -> None:
    """Batch-refresh citation_count (and backfill oa_pdf_url) from Semantic Scholar."""
    targets = [(p, qid) for p in papers if (qid := s2_query_id(p))]
    if not targets:
        return
    headers = {}
    if key := os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip():
        headers["x-api-key"] = key
    url = f"{S2_BATCH_URL}?fields=citationCount,openAccessPdf,externalIds"

    for batch in _chunks(targets, S2_BATCH_SIZE):
        ids = [qid for _, qid in batch]
        resp = _post(url, {"ids": ids}, headers)
        if not isinstance(resp, list):
            continue  # whole batch failed → leave those papers untouched
        for (entry, _), rec in zip(batch, resp, strict=False):  # response aligns to input order
            if not isinstance(rec, dict):
                continue  # null = not found
            _apply_citation(entry, _valid_citation(rec.get("citationCount")), stats)
            _apply_oa(entry, _oa_url(rec.get("openAccessPdf")), stats)
        time.sleep(1.0)  # polite to the shared endpoint between batches


def refresh_from_openalex(papers: list[dict], stats: dict) -> None:
    """Fallback citation refresh via OpenAlex (no key needed) for papers with a DOI."""
    todo = [p for p in papers if p.get("doi") and p.get("key") not in stats["_s2_hit"]]
    if not todo:
        return
    mailto = os.environ.get("OPENALEX_MAILTO", "").strip()
    by_doi = {p["doi"].lower(): p for p in todo}

    for batch in _chunks(list(by_doi), OA_PAGE_SIZE):
        flt = "doi:" + "|".join(batch)
        url = f"{OPENALEX_URL}?filter={quote(flt, safe=':|')}&per-page={OA_PAGE_SIZE}"
        url += "&select=ids,cited_by_count,open_access"
        if mailto:
            url += f"&mailto={quote(mailto)}"
        resp = _get(url)
        results = (resp or {}).get("results", []) if isinstance(resp, dict) else []
        for rec in results:
            doi_url = ((rec.get("ids") or {}).get("doi") or "").lower()
            doi = doi_url.replace("https://doi.org/", "")
            entry = by_doi.get(doi)
            if not entry:
                continue
            _apply_citation(entry, _valid_citation(rec.get("cited_by_count")), stats)
            oa = rec.get("open_access") or {}
            _apply_oa(entry, oa.get("oa_url") if oa.get("is_oa") else None, stats)
        time.sleep(0.2)


def refresh_oa_from_unpaywall(papers: list[dict], stats: dict, workers: int = 8) -> None:
    """Backfill oa_pdf_url from Unpaywall for papers that still lack an OA link."""
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    if not email:
        print("  Unpaywall: UNPAYWALL_EMAIL not set — skipping OA backfill")
        return
    todo = [p for p in papers if p.get("doi") and not p.get("oa_pdf_url")]
    if not todo:
        return

    def lookup(entry):
        url = f"{UNPAYWALL_URL}/{quote(entry['doi'])}?email={quote(email)}"
        data = _get(url)
        if isinstance(data, dict):
            loc = data.get("best_oa_location") or {}
            return entry, loc.get("url_for_pdf") or loc.get("url")
        return entry, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for entry, oa in pool.map(lookup, todo):
            _apply_oa(entry, oa, stats)


# --------------------------------------------------------------------------- #
# mutation + bookkeeping
# --------------------------------------------------------------------------- #
def _apply_citation(entry: dict, fresh: int | None, stats: dict) -> None:
    if fresh is None:
        return
    stats["_s2_hit"].add(entry.get("key"))  # mark as resolved (skip OpenAlex fallback)
    old = entry.get("citation_count") or 0
    if fresh != old:
        entry["citation_count"] = fresh
        stats["citations_updated"] += 1
        stats["total_citation_delta"] += fresh - old


def _apply_oa(entry: dict, url: str | None, stats: dict) -> None:
    if url and not entry.get("oa_pdf_url"):
        entry["oa_pdf_url"] = url
        stats["oa_links_added"] += 1


# --------------------------------------------------------------------------- #
# validation (refuse to write a corrupted corpus)
# --------------------------------------------------------------------------- #
def validate(corpus: dict, prev_count: int, prev_first_seen: dict) -> list[str]:
    errors = []
    papers = corpus["papers"]
    if len(papers) != prev_count:
        errors.append(
            f"paper count changed {prev_count} -> {len(papers)} (refresh must not add/drop)"
        )
    for p in papers:
        if "abstract" in p:
            errors.append("abstract leaked into a corpus entry")
            break
        k = p.get("key")
        if k in prev_first_seen and p.get("first_seen") != prev_first_seen[k]:
            errors.append(f"first_seen mutated for {k}")
            break
    try:
        json.loads(json.dumps(corpus, ensure_ascii=False))
    except Exception as ex:  # noqa: BLE001
        errors.append(f"corpus not serializable/parseable: {ex}")
    return errors


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="corpus.json")
    ap.add_argument("--dry-run", action="store_true", help="report deltas, write nothing")
    ap.add_argument("--max-papers", type=int, default=0, help="limit (for testing only)")
    ap.add_argument("--workers", type=int, default=8, help="Unpaywall concurrency")
    a = ap.parse_args()

    with open(a.corpus, encoding="utf-8") as f:
        corpus = json.load(f)
    papers = corpus.get("papers", [])
    if a.max_papers:
        papers = papers[: a.max_papers]
    if not papers:
        print("Corpus has no papers — nothing to refresh.")
        return 0

    prev_count = len(corpus["papers"])
    prev_first_seen = {p.get("key"): p.get("first_seen") for p in corpus["papers"]}
    today = datetime.date.today().isoformat()
    stats = {
        "citations_updated": 0,
        "total_citation_delta": 0,
        "oa_links_added": 0,
        "_s2_hit": set(),
    }

    print(f"Refreshing {len(papers)} papers (corpus has {prev_count})...")
    refresh_from_s2(papers, stats)
    print(f"  Semantic Scholar: resolved {len(stats['_s2_hit'])} papers")
    refresh_from_openalex(papers, stats)
    refresh_oa_from_unpaywall(papers, stats, workers=a.workers)

    # stamp a per-paper refresh clock on everything we examined (first_seen untouched)
    for p in papers:
        p["last_refreshed"] = today

    stats.pop("_s2_hit")
    refresh_record = {
        "refresh_id": f"refresh-{today}",
        "refreshed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "papers_examined": len(papers),
        **stats,
    }

    print(
        f"\nDeltas: {stats['citations_updated']} papers changed citations "
        f"(net {stats['total_citation_delta']:+d}), "
        f"{stats['oa_links_added']} OA links added."
    )

    if a.dry_run:
        print("--dry-run: corpus NOT written.")
        return 0

    corpus["refreshes"] = corpus.get("refreshes", []) + [refresh_record]
    corpus["last_refreshed_at"] = refresh_record["refreshed_at"]
    corpus["corpus_updated_at"] = refresh_record["refreshed_at"]

    errors = validate(corpus, prev_count, prev_first_seen)
    if errors:
        print("VALIDATION FAILED — corpus NOT written:", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        return 1

    tmp = a.corpus + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(corpus, ensure_ascii=False, indent=2))
    os.replace(tmp, a.corpus)
    print(f"Wrote {a.corpus} (refresh {refresh_record['refresh_id']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
