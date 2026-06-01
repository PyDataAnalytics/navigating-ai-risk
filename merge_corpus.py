#!/usr/bin/env python3
"""
merge_corpus.py - merge a retrieval run (latest.json) into the durable corpus.json.

Model A (paper-centric): one entry per UNIQUE paper, with a list of `placements`
(the category/subcategory slots it was selected for, each carrying its own
composite_score / llm_relevance / rationale). No paper metadata is duplicated.

Two clocks per paper:
  first_seen - run date the paper first entered the corpus (NEVER changes)
  last_seen  - most recent run that selected it
This is what powers "what's new this week" without faking publication dates.

Copyright: the published corpus carries NO abstract. The archived raw snapshot is
ALSO stripped of abstracts, so it is safe to commit and is sufficient to rebuild the
corpus. Full-fidelity (with abstracts) stays only in the original latest.json.

Safety: dedup-on-write, idempotent per run_id, validate-before-write, atomic replace.

Usage:
  python merge_corpus.py --run data/output/latest.json --corpus corpus.json \
                         --snapshot-dir snapshots
"""

import argparse
import copy
import datetime
import json
import os
import sys

CORPUS_SCHEMA = "1.0"


# ---------- helpers ----------
def norm(s):
    return s.strip().lower() if isinstance(s, str) and s.strip() else None


def paper_key(p):
    """Dedup identity: doi -> arxiv_id -> semantic_scholar_id -> content_hash -> title."""
    for k in ("doi", "arxiv_id", "semantic_scholar_id"):
        v = norm(p.get(k))
        if v:
            return f"{k}:{v}"
    ch = norm(p.get("content_hash"))
    if ch:
        return f"content_hash:{ch}"
    t = norm(p.get("title"))
    return f"title:{t}" if t else None


def author_names(authors):
    out = []
    for a in authors or []:
        if isinstance(a, str):
            out.append(a)
        elif isinstance(a, dict):
            out.append(a.get("name") or a.get("display_name") or "")
    return [a for a in out if a]


def published_meta(p):
    """Bibliographic metadata only - explicitly NO abstract."""
    return {
        "title": p.get("title") or "Untitled",
        "authors": author_names(p.get("authors")),
        "year": p.get("year"),
        "publication_date": p.get("publication_date"),
        "venue": p.get("venue") or "",
        "citation_count": p.get("citation_count") or 0,
        "doi": p.get("doi"),
        "arxiv_id": p.get("arxiv_id"),
        "semantic_scholar_id": p.get("semantic_scholar_id"),
        "url": p.get("url") or "",
        "pdf_url": p.get("pdf_url") or "",
        "oa_pdf_url": p.get("oa_pdf_url") or "",
        "source": p.get("source") or "",
        "content_hash": p.get("content_hash"),
    }


def strip_abstracts(run):
    r = copy.deepcopy(run)
    for res in r.get("results", []):
        for sp in res.get("selected_papers", []):
            (sp.get("paper") or {}).pop("abstract", None)
    return r


def run_date(run):
    return (run.get("finished_at") or run.get("started_at") or "")[:10]


def load_corpus(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "schema_version": CORPUS_SCHEMA,
        "taxonomy_version": None,
        "corpus_updated_at": None,
        "runs": [],
        "taxonomy": [],
        "papers": [],
    }


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument(
        "--snapshot-dir",
        default=None,
        help="if set, archive an abstract-stripped copy of the run here (safe to commit)",
    )
    a = ap.parse_args()

    with open(a.run, encoding="utf-8") as f:
        run = json.load(f)
    results = run.get("results", [])
    rid = run.get("run_id")
    rdate = run_date(run)

    corpus = load_corpus(a.corpus)
    prev_count = len(corpus["papers"])
    by_key = {e["key"]: e for e in corpus["papers"]}
    prev_first_seen = {k: e.get("first_seen") for k, e in by_key.items()}

    # idempotency: never merge the same run twice (would double-count)
    if any(r.get("run_id") == rid for r in corpus["runs"]):
        print(f"Run {rid} already merged into corpus - nothing to do.")
        return

    seen_this_run, papers_added, placements_touched = set(), 0, 0

    for r in results:
        cid, cname = r.get("category_id"), r.get("category_name")
        sub, gen = r.get("subcategory_name"), r.get("generated_at")
        for sp in r.get("selected_papers") or []:
            p = sp.get("paper") or {}
            key = paper_key(p)
            if not key:
                continue
            placement = {
                "category_id": cid,
                "category_name": cname,
                "subcategory_name": sub,
                "composite_score": sp.get("composite_score"),
                "llm_relevance": (sp.get("llm") or {}).get("relevance"),
                "rationale": (sp.get("llm") or {}).get("rationale") or "",
                "run_id": rid,
                "generated_at": gen,
            }
            entry = by_key.get(key)
            if entry is None:
                entry = {
                    "key": key,
                    "first_seen": rdate,
                    "last_seen": rdate,
                    **published_meta(p),
                    "placements": [placement],
                }
                by_key[key] = entry
                corpus["papers"].append(entry)
                papers_added += 1
                placements_touched += 1
            else:
                entry["last_seen"] = rdate
                fresh = published_meta(p)  # refresh mutable fields to latest run
                entry["citation_count"] = fresh["citation_count"]
                if fresh["oa_pdf_url"]:
                    entry["oa_pdf_url"] = fresh["oa_pdf_url"]
                slot = next(
                    (
                        pl
                        for pl in entry["placements"]
                        if pl["category_id"] == cid and pl["subcategory_name"] == sub
                    ),
                    None,
                )
                if slot is None:
                    entry["placements"].append(placement)
                else:
                    slot.update(placement)
                placements_touched += 1
            seen_this_run.add(key)

    corpus["schema_version"] = CORPUS_SCHEMA
    corpus["taxonomy_version"] = run.get("taxonomy_version") or corpus.get("taxonomy_version")
    corpus["corpus_updated_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    corpus["runs"].append(
        {
            "run_id": rid,
            "finished_at": run.get("finished_at"),
            "merged_at": corpus["corpus_updated_at"],
            "papers_selected": len(seen_this_run),
            "llm_model": run.get("llm_model"),
        }
    )

    # capture the FULL taxonomy (every category + subcategory in run order, incl.
    # 0-paper subcats) so the corpus can power the coverage view and preserve order.
    tax, tseen = [], {}
    for r in results:
        cid = r.get("category_id")
        if cid not in tseen:
            tseen[cid] = {
                "category_id": cid,
                "category_name": r.get("category_name"),
                "subcategories": [],
            }
            tax.append(tseen[cid])
        tseen[cid]["subcategories"].append(r.get("subcategory_name"))
    corpus["taxonomy"] = tax

    # ---- validate BEFORE writing ----
    new_count = len(corpus["papers"])
    errors = []
    if new_count < prev_count:
        errors.append(f"paper count shrank {prev_count} -> {new_count}")
    for k, fs in prev_first_seen.items():
        if by_key[k].get("first_seen") != fs:
            errors.append(f"first_seen mutated for existing paper {k}")
            break
    for e in corpus["papers"]:
        if "abstract" in e:
            errors.append("abstract leaked into corpus entry")
            break
    try:
        text = json.dumps(corpus, ensure_ascii=False, indent=2)
        json.loads(text)
    except Exception as ex:
        errors.append(f"corpus not serializable/parseable: {ex}")
    if errors:
        print("VALIDATION FAILED - corpus NOT written:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    # ---- archive stripped raw snapshot (safe to commit; rebuilds corpus) ----
    if a.snapshot_dir:
        dst = os.path.join(a.snapshot_dir, rdate)
        os.makedirs(dst, exist_ok=True)
        with open(os.path.join(dst, f"run-{rid}.json"), "w", encoding="utf-8") as f:
            json.dump(strip_abstracts(run), f, ensure_ascii=False)

    # ---- atomic write ----
    tmp = a.corpus + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, a.corpus)

    print(f"Merged run {rid} ({rdate}).")
    print(f"  unique papers in corpus: {prev_count} -> {new_count}  (+{papers_added} new)")
    print(f"  placements added/updated: {placements_touched}")
    print(f"  unique papers selected this run: {len(seen_this_run)}")
    if a.snapshot_dir:
        print(
            f"  raw snapshot (abstract-stripped) archived: {a.snapshot_dir}/{rdate}/run-{rid}.json"
        )


if __name__ == "__main__":
    main()
