#!/usr/bin/env python3
"""Standalone Unpaywall enrichment: fills oa_pdf_url on papers that have a DOI.
Runs over an existing run file (latest.json) - no GPU, no re-retrieval.
Standard library only (no pip install needed)."""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def best_oa_pdf(doi, email, timeout=20.0):
    url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={quote(email)}"
    req = Request(url, headers={"User-Agent": f"ai-risk-retrieval (mailto:{email})"})
    with urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    loc = data.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url")  # PDF if available, else landing page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True, type=Path)
    ap.add_argument("--email", "-e", required=True)
    ap.add_argument(
        "--output", "-o", type=Path, default=None, help="defaults to overwriting --input"
    )
    args = ap.parse_args()
    out = args.output or args.input

    run = json.loads(args.input.read_text(encoding="utf-8"))
    papers = [sp["paper"] for r in run["results"] for sp in r.get("selected_papers", [])]
    todo = [p for p in papers if p.get("doi") and not p.get("oa_pdf_url")]
    print(
        f"{len(papers)} papers, {len(todo)} with a DOI and no OA link yet - querying Unpaywall..."
    )

    filled = errors = 0
    for i, p in enumerate(todo, 1):
        try:
            pdf = best_oa_pdf(p["doi"], args.email)
            if pdf:
                p["oa_pdf_url"] = pdf
                filled += 1
        except HTTPError as e:
            errors += 1
            if e.code != 404:  # 404 = DOI not in Unpaywall, normal
                print(f"  [{i}] HTTP {e.code} for {p['doi']}", file=sys.stderr)
        except (URLError, TimeoutError, Exception) as e:
            errors += 1
            print(f"  [{i}] {type(e).__name__} for {p.get('doi')}", file=sys.stderr)
        if i % 25 == 0:
            print(f"  ...{i}/{len(todo)}  (filled {filled})")
        time.sleep(0.1)  # polite to the free API

    out.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. Filled oa_pdf_url on {filled} papers, {errors} misses/errors.\nWrote {out}")


if __name__ == "__main__":
    main()
