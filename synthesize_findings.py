#!/usr/bin/env python3
"""Evidence digest builder: corpus.json + excerpts.json -> syntheses.json (+ docs/syntheses.js).

For each of the 16 AI-risk categories, gathers the key findings of the papers
placed in it (from the excerpt step) and asks a self-hosted LLM to ORGANISE them
into a short, cited digest -- it may only restate and group the findings, never
conclude beyond them. Output feeds the "Evidence" tab (window.SYNTHESES).

Privacy-first: this runs entirely against a self-hosted Ollama. No paper content
and no derived data is ever sent to a third-party API.

Usage (on the pod, with Ollama serving the model):
  python synthesize_findings.py --model qwen2.5:32b
  python synthesize_findings.py --model qwen2.5:32b --host http://localhost:11434
"""

import argparse
import datetime
import json
import os

import requests

# --- category split (kept in sync with build_data.py) ---
TECHNOLOGY = {
    "Failure under adversarial inputs",
    "Prompt injection attacks",
    "Jailbreaks",
    "Adversarial examples",
    "Data poisoning",
    "Unexpected emergent behaviors",
    "Objective misspecification",
    "Reward hacking",
    "Wireheading",
    "Proxy gaming",
    "Goal misgeneralization",
    "Instrumental convergence",
    "Deceptive alignment",
    "Inner misalignment",
    "Specification gaming",
}
CATEGORY_ORDER = [
    "technology",
    "reliability",
    "safety",
    "security_cyber",
    "privacy",
    "ethical",
    "social_cultural",
    "economic_labor",
    "political_geopolitical",
    "legal_compliance",
    "organizational_business",
    "environmental",
    "cognitive_psychological",
    "scientific_knowledge",
    "existential",
    "meta_risks",
]
SPLIT_NAMES = {"technology": "Technology", "reliability": "Reliability"}


def effective_cat(cid, subname):
    if cid != "technical_reliability":
        return cid
    return "technology" if subname in TECHNOLOGY else "reliability"


# ---------------------------------------------------------------- self-hosted LLM
def _parse_json(s):
    s = (s or "").strip()
    i, j = s.find("{"), s.rfind("}")
    if i == -1 or j == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(s[i : j + 1])


class OllamaClient:
    def __init__(self, model, host, timeout=240):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def complete(self, prompt):
        r = requests.post(
            f"{self.host}/api/generate",
            timeout=self.timeout,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
        )
        r.raise_for_status()
        return _parse_json(r.json().get("response", ""))


# ---------------------------------------------------------------- data prep
def load_inputs(corpus_path, excerpts_path):
    corpus = json.load(open(corpus_path, encoding="utf-8"))
    ex = json.load(open(excerpts_path, encoding="utf-8")).get("excerpts", {})
    findings = {}
    for k, r in ex.items():
        if r.get("status") == "ok" and r.get("excerpt"):
            kf = [
                f
                for f in (r["excerpt"].get("key_findings") or [])
                if isinstance(f, str) and f.strip()
            ]
            if kf:
                findings[k] = kf
    return corpus, findings


def paper_meta(corpus):
    m = {}
    for e in corpus.get("papers", []):
        doi = e.get("doi")
        url = (
            e.get("url")
            or (f"https://doi.org/{doi}" if doi else "")
            or e.get("oa_pdf_url")
            or e.get("pdf_url")
            or ""
        )
        m[e.get("key")] = {"title": e.get("title") or "Untitled", "year": e.get("year"), "url": url}
    return m


def group_by_category(corpus, findings, meta):
    cat_name, order, cat_papers = {}, [], {}
    for t in corpus.get("taxonomy", []):
        cid0, cname = t.get("category_id"), t.get("category_name")
        for sub in t.get("subcategories", []):
            cid = effective_cat(cid0, sub)
            if cid not in cat_name:
                cat_name[cid] = SPLIT_NAMES.get(cid, cname)
                cat_papers[cid] = {}
                order.append(cid)
    for e in corpus.get("papers", []):
        k = e.get("key")
        if k not in findings:
            continue
        for pl in e.get("placements", []):
            cid = effective_cat(pl.get("category_id"), pl.get("subcategory_name"))
            if cid in cat_papers:
                cat_papers[cid].setdefault(
                    k, {**meta.get(k, {}), "key": k, "findings": findings[k]}
                )
    ids = [c for c in CATEGORY_ORDER if c in cat_name] + [
        c for c in order if c not in CATEGORY_ORDER
    ]
    return [(cid, cat_name[cid], list(cat_papers[cid].values())) for cid in ids]


# ---------------------------------------------------------------- prompt + assemble
def build_prompt(cname, papers, max_papers=80):
    papers = papers[:max_papers]
    refmap, lines = {}, []
    for i, p in enumerate(papers, 1):
        refmap[i] = p
        yr = f" ({p['year']})" if p.get("year") else ""
        lines.append(f"[{i}] {p.get('title', 'Untitled')}{yr}: " + "; ".join(p["findings"]))
    prompt = (
        f'You are building an evidence digest for the AI-risk category "{cname}".\n'
        f"Below are key findings extracted from {len(papers)} research papers in this category, each numbered.\n\n"
        + "\n".join(lines)
        + "\n\nOrganise these findings into a short digest. Rules:\n"
        "- Group related findings into 3 to 6 points.\n"
        "- Each point restates, in your own words, what the research found, and cites the paper "
        "number(s) it comes from, e.g. [1] or [2,4].\n"
        "- Use ONLY the findings above. Do not add claims, conclusions, recommendations, or outside knowledge.\n"
        "- Keep each point to one or two sentences.\n"
        "- Also give a one-sentence overview of what this body of work covers (no conclusions beyond the findings).\n"
        'Respond with JSON only: {"overview": "...", "points": [{"point": "...", "refs": [1, 3]}]}'
    )
    return prompt, refmap


def assemble(cid, cname, papers, data, refmap):
    pts = []
    for pt in data.get("points", []):
        text = (pt.get("point") or "").strip()
        if not text:
            continue
        cited = []
        for n in pt.get("refs", []):
            p = refmap.get(int(n)) if str(n).isdigit() else None
            if p:
                cited.append(
                    {
                        "title": p.get("title"),
                        "year": p.get("year"),
                        "url": p.get("url"),
                        "key": p.get("key"),
                    }
                )
        pts.append({"point": text, "papers": cited})
    return {
        "id": cid,
        "name": cname,
        "nPapers": len(papers),
        "nFindings": sum(len(p["findings"]) for p in papers),
        "overview": (data.get("overview") or "").strip(),
        "points": pts,
        "status": "ok",
    }


# ---------------------------------------------------------------- output
def _atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def write_outputs(out_path, js_path, model, results):
    cats = list(results.values())
    now = datetime.datetime.now(datetime.UTC).isoformat()
    full = {
        "schema_version": "1.0",
        "model": model,
        "self_hosted": True,
        "generated_at": now,
        "categories": cats,
    }
    _atomic(out_path, json.dumps(full, ensure_ascii=False, indent=2))
    js = {"generated": now[:10], "model": model, "categories": cats}
    os.makedirs(os.path.dirname(js_path) or ".", exist_ok=True)
    _atomic(js_path, "window.SYNTHESES = " + json.dumps(js, ensure_ascii=False) + ";\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="corpus.json")
    ap.add_argument("--excerpts", default="excerpts.json")
    ap.add_argument("--out", default="syntheses.json")
    ap.add_argument("--js", default="docs/syntheses.js")
    ap.add_argument("--model", default="qwen2.5:32b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--min-papers", type=int, default=1, help="skip categories with fewer papers")
    ap.add_argument("--limit", type=int, default=0, help="only first N categories (testing)")
    a = ap.parse_args()

    corpus, findings = load_inputs(a.corpus, a.excerpts)
    groups = group_by_category(corpus, findings, paper_meta(corpus))
    if a.limit:
        groups = groups[: a.limit]

    done = {}
    if os.path.exists(a.out):
        prev = json.load(open(a.out, encoding="utf-8"))
        done = {c["id"]: c for c in prev.get("categories", []) if c.get("status") == "ok"}

    client = OllamaClient(a.model, a.host)
    results = {}
    for cid, cname, papers in groups:
        if cid in done:
            results[cid] = done[cid]
            print(f"skip {cname} (cached)")
            continue
        if len(papers) < a.min_papers:
            results[cid] = {
                "id": cid,
                "name": cname,
                "nPapers": len(papers),
                "nFindings": 0,
                "overview": "",
                "points": [],
                "status": "skipped_no_papers",
            }
            print(f"skip {cname} ({len(papers)} papers)")
            continue
        prompt, refmap = build_prompt(cname, papers)
        try:
            data = client.complete(prompt)
            results[cid] = assemble(cid, cname, papers, data, refmap)
            print(f"ok   {cname}: {len(results[cid]['points'])} points from {len(papers)} papers")
        except Exception as e:
            results[cid] = {
                "id": cid,
                "name": cname,
                "nPapers": len(papers),
                "nFindings": 0,
                "overview": "",
                "points": [],
                "status": "llm_failed",
            }
            print(f"FAIL {cname}: {e}")
        write_outputs(a.out, a.js, a.model, results)
    write_outputs(a.out, a.js, a.model, results)
    ok = sum(1 for c in results.values() if c.get("status") == "ok")
    print(f"\n{ok}/{len(results)} categories have a digest -> {a.out}, {a.js}")


if __name__ == "__main__":
    main()
