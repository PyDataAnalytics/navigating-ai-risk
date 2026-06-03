#!/usr/bin/env python3
"""Adapter: corpus.json -> risk_data.js (window.RISK) for the Home / Explorer /
Coverage / Landscape / Mind Map / 3D Graph views.

Reads the durable, paper-centric corpus (model A) and inverts it into the
category -> subcategory -> papers tree the views render. Uses the corpus's
embedded `taxonomy` for full structure + order (incl. 0-paper subcategories),
and attaches selected papers from `papers`. Splits the 'Technical & Reliability
Risks' category into 'Technology' and 'Reliability'. Carries first_seen/last_seen
through so the views can flag what's new. No abstract (corpus is abstract-free).

Usage: python build_data.py -i corpus.json -o docs/risk_data.js
"""
import argparse
import datetime
import json
import os
from collections import defaultdict

# --- split of technical_reliability's subcategories (edit freely) ---
TECHNOLOGY = {
    "Failure under adversarial inputs","Prompt injection attacks","Jailbreaks","Adversarial examples",
    "Data poisoning","Unexpected emergent behaviors","Objective misspecification","Reward hacking",
    "Wireheading","Proxy gaming","Goal misgeneralization","Instrumental convergence","Deceptive alignment",
    "Inner misalignment","Specification gaming",
}
RELIABILITY = {
    "Hallucinations","Fabricated citations or sources","Incorrect reasoning","Arithmetic and logical errors",
    "Misunderstanding context or intent","Overfitting and underfitting","Brittleness outside training distribution",
    "Distribution shift failures","Catastrophic forgetting","Unpredictable outputs","Non-determinism in LLMs",
    "Cascading system failures","Automation complacency","Silent degradation over time",
    "Poor monitoring or observability","Dependency on external APIs and models",
}

# canonical presentation order of the 16 categories (taxonomy v1.0, with the split)
CATEGORY_ORDER = [
    "technology", "reliability", "safety", "security_cyber", "privacy",
    "ethical", "social_cultural", "economic_labor", "political_geopolitical",
    "legal_compliance", "organizational_business", "environmental",
    "cognitive_psychological", "scientific_knowledge", "existential", "meta_risks",
]
SPLIT_NAMES = {"technology": "Technology", "reliability": "Reliability"}

def effective_cat(cid, subname):
    """Route technical_reliability placements into the Technology/Reliability split."""
    if cid != "technical_reliability":
        return cid
    return "technology" if subname in TECHNOLOGY else "reliability"  # leftover -> reliability

def pub_display(iso):
    """Publication date for display, degrading gracefully:
    '2024-11-20' -> '20 November 2024', '2024-11' -> 'November 2024',
    '2024' -> '2024'. Empty string when unknown. Cross-platform (no %-d)."""
    s = (iso or "").strip()
    if not s:
        return ""
    try:
        d = datetime.date.fromisoformat(s[:10])
        return f"{d.day} {d.strftime('%B')} {d.year}"
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(s[:7], "%Y-%m").strftime("%B %Y")
    except ValueError:
        pass
    return s[:4] if s[:4].isdigit() else s


def paper_for(entry, pl, excerpts):
    authors = entry.get("authors") or []
    doi = entry.get("doi")
    landing = (entry.get("url") or (f"https://doi.org/{doi}" if doi else "")
               or entry.get("oa_pdf_url") or entry.get("pdf_url") or "")
    return {
        "title": entry.get("title") or "Untitled",
        "authors": authors[:3],
        "nAuthors": len(authors),
        "year": entry.get("year"),
        "published": pub_display(entry.get("publication_date")),  # e.g. "20 November 2024"
        "venue": entry.get("venue") or "",
        "citations": entry.get("citation_count") or 0,
        "score": pl.get("composite_score"),
        "relevance": pl.get("llm_relevance"),
        "rationale": pl.get("rationale") or "",
        "abstract": "",                                  # corpus is abstract-free by design
        "source": entry.get("source") or "",
        "url": landing,                                  # landing page - opens in the browser
        "pdf": entry.get("oa_pdf_url") or entry.get("pdf_url") or "",  # full-text PDF (may download)
        "excerpt": excerpts.get(entry.get("key")),       # {summary, key_findings, risk_relevance, ...} or None
        "first_seen": entry.get("first_seen"),
        "last_seen": entry.get("last_seen"),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i","--input", required=True, help="corpus.json")
    ap.add_argument("-o","--output", required=True, help="docs/risk_data.js")
    ap.add_argument("-e","--excerpts", default="excerpts.json",
                    help="excerpts.json - folded in if present (optional)")
    a = ap.parse_args()
    corpus = json.load(open(a.input, encoding="utf-8"))
    papers = corpus.get("papers", [])
    taxonomy = corpus.get("taxonomy", [])
    if not taxonomy:
        raise SystemExit("corpus has no `taxonomy` block - regenerate it with the updated merge_corpus.py")

    # load excerpts (corpus key -> excerpt object) for papers with an `ok` summary
    excerpts = {}
    if os.path.exists(a.excerpts):
        ex = json.load(open(a.excerpts, encoding="utf-8"))
        for k, r in ex.get("excerpts", {}).items():
            if r.get("status") == "ok" and r.get("excerpt"):
                excerpts[k] = r["excerpt"]

    # (category_id, subcategory_name) -> [paper objects]
    bucket = defaultdict(list)
    for entry in papers:
        for pl in entry.get("placements", []):
            bucket[(pl.get("category_id"), pl.get("subcategory_name"))].append(paper_for(entry, pl, excerpts))

    # build effective categories from the taxonomy, applying the split, preserving subcat order
    cat_name, cat_subs, first_order = {}, {}, []
    for t in taxonomy:
        cid0, cname = t.get("category_id"), t.get("category_name")
        for sub in t.get("subcategories", []):
            cid = effective_cat(cid0, sub)
            if cid not in cat_subs:
                cat_subs[cid] = []
                cat_name[cid] = SPLIT_NAMES.get(cid, cname)
                first_order.append(cid)
            cat_subs[cid].append((sub, bucket.get((cid0, sub), [])))

    # emit categories in canonical order (unknown ids appended after)
    ids = [c for c in CATEGORY_ORDER if c in cat_subs] + [c for c in first_order if c not in CATEGORY_ORDER]
    categories = []
    for cid in ids:
        subs = cat_subs[cid]
        categories.append({
            "id": cid,
            "name": cat_name[cid],
            "papers": sum(len(ps) for _, ps in subs),
            "subs": [{"name": n, "papers": ps} for (n, ps) in subs],
        })

    total = sum(c["papers"] for c in categories)
    runs = corpus.get("runs", [])
    last = runs[-1] if runs else {}
    def fmt(iso):
        try:
            return datetime.datetime.fromisoformat((iso or "").replace("Z","+00:00")).strftime("%d %B %Y")
        except Exception:
            return iso or ""

    RISK = {
        "generated": fmt(last.get("finished_at") or corpus.get("corpus_updated_at")),
        "model": last.get("llm_model") or "",
        "taxonomy_version": corpus.get("taxonomy_version",""),
        "totalPapers": total,                                   # placements (matches per-category sums)
        "uniquePapers": len(papers),                            # distinct papers in the corpus
        "excerptCount": len(excerpts),                          # papers with an AI summary
        "latestRun": (last.get("finished_at") or corpus.get("corpus_updated_at") or "")[:10],
        "runCount": len(runs),
        "categories": categories,
    }
    with open(a.output, "w", encoding="utf-8") as f:
        f.write("window.RISK = " + json.dumps(RISK, ensure_ascii=False) + ";\n")
    total_subs = sum(len(c["subs"]) for c in categories)
    covered = sum(1 for c in categories for s in c["subs"] if s["papers"])
    print(f"Wrote {a.output}")
    print(f"  {len(categories)} categories | {total_subs} subcategories ({covered} covered, {total_subs-covered} empty)")
    print(f"  {total} placements across {len(papers)} unique papers")
    print(f"  {len(excerpts)} papers have a summary folded in")

if __name__ == "__main__":
    main()
