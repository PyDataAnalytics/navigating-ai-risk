#!/usr/bin/env python3
"""
excerpt_agent.py - generate copyright-safe, own-words excerpts for corpus papers.

Reads corpus.json, fetches each paper's open-access PDF, extracts text, and asks a
local LLM (Ollama by default) for a plain-language summary + structured findings +
risk relevance - in the model's OWN WORDS, with no verbatim quotes. Output is JSON
keyed by the corpus paper key, cached so only NEW papers are processed each run.

Built with clean seams so it can be repointed at other corpora later:
  - SOURCE adapter  (iter_documents) : the ONLY corpus-specific part
  - EXTRACTOR       (extract_text)   : PDF -> text, format-agnostic
  - MODEL backend   (LLMClient)      : Ollama now; swap by reimplementing .complete()
  - SUMMARIZER core (summarize)      : (text, context) -> structured excerpt; corpus-agnostic
To reuse on regulatory / internal docs: write a new iter_documents + tweak SCHEMA below.

Usage:
  python excerpt_agent.py --corpus corpus.json --out excerpts.json \
      --model llama3.1:70b --ollama-url http://localhost:11434
  # smoke-test a few first:
  python excerpt_agent.py --corpus corpus.json --out excerpts.json --model llama3.1:8b --limit 3
"""

import argparse
import datetime
import io
import json
import os
import sys
import time

try:
    import pdfplumber
    import requests
except ImportError as e:
    sys.exit(f"Missing dependency: {e.name}. Run:  pip install requests pdfplumber")

EXCERPT_SCHEMA = "1.0"
DEFAULT_MAX_CHARS = 24000  # ~6k tokens of document text; caps latency/cost (head of doc)
MIN_TEXT_CHARS = 300  # below this we treat extraction as failed (scanned/paywalled)


def now_iso():
    return datetime.datetime.now(datetime.UTC).isoformat()


# ---------------- MODEL BACKEND (swappable) ----------------
class LLMClient:
    """One interface for the language model. Ollama implementation.
    To add an API backend later, implement a class with the same .complete(prompt)."""

    def __init__(self, model, base_url="http://localhost:11434", timeout=240):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, prompt):
        r = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # ask Ollama to emit valid JSON
                "options": {"temperature": 0.2},
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("response", "")


# ---------------- SUMMARIZER CORE (corpus-agnostic) ----------------
SCHEMA = (
    "{\n"
    '  "summary": "2-4 sentence plain-language summary, in your own words",\n'
    '  "key_findings": ["3-6 concise findings, each in your own words"],\n'
    '  "methods": "1 sentence on the approach/method, or empty string",\n'
    '  "risk_relevance": "how this relates to the stated risk area(s), your own words",\n'
    '  "limitations": "1 sentence on limitations/caveats, or empty string"\n'
    "}"
)
INSTRUCTIONS = (
    "You are a precise research analyst writing for a knowledge professional. "
    "Summarize the document below. Write ENTIRELY IN YOUR OWN WORDS - do NOT quote, "
    "copy, or closely paraphrase any sentence or phrase from the text. Be accurate; "
    "if something is unclear or not stated, say so rather than inventing it. "
    "Return ONLY a valid JSON object with exactly this shape:\n" + SCHEMA
)


def build_prompt(text, context):
    return (
        INSTRUCTIONS
        + f"\n\nRISK CONTEXT (why this document was selected): {context}"
        + f'\n\nDOCUMENT TEXT (may be truncated):\n"""\n{text}\n"""'
        + "\n\nRemember: your own words only, no quotes. Return only the JSON object."
    )


def parse_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        s, e = raw.find("{"), raw.rfind("}")  # salvage a wrapped object
        if s != -1 and e > s:
            return json.loads(raw[s : e + 1])
        raise


def summarize(llm, text, context):
    data = parse_json(llm.complete(build_prompt(text, context)))
    return {
        "summary": (data.get("summary") or "").strip(),
        "key_findings": [
            str(x).strip() for x in (data.get("key_findings") or []) if str(x).strip()
        ],
        "methods": (data.get("methods") or "").strip(),
        "risk_relevance": (data.get("risk_relevance") or "").strip(),
        "limitations": (data.get("limitations") or "").strip(),
    }


# ---------------- EXTRACTOR (format-agnostic; PDF here) ----------------
def fetch_bytes(url, timeout=60):
    headers = {
        "User-Agent": "ai-risk-retrieval excerpt-agent (+https://github.com/PyDataAnalytics/navigating-ai-risk)"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.content


def extract_text(pdf_bytes, max_chars=DEFAULT_MAX_CHARS):
    parts, total = [], 0
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t:
                parts.append(t)
                total += len(t)
            if total >= max_chars:
                break
    return "\n".join(parts).strip()[:max_chars]


# ---------------- SOURCE ADAPTER (the only AI-risk-specific part) ----------------
def iter_documents(corpus):
    """Yield {id, title, url, context} per paper.
    Swap THIS function to repoint the agent at a different corpus."""
    for p in corpus.get("papers", []):
        url = p.get("oa_pdf_url") or p.get("pdf_url") or ""
        areas = [
            f"{pl.get('subcategory_name')} ({pl.get('category_name')})"
            for pl in p.get("placements", [])
        ]
        context = "; ".join(dict.fromkeys(areas)) or "AI risk research"
        yield {
            "id": p.get("key") or p.get("content_hash") or p.get("doi") or p.get("title"),
            "title": p.get("title") or "Untitled",
            "url": url,
            "context": context,
        }


# ---------------- ORCHESTRATION ----------------
def process_one(llm, d, max_chars):
    rec = {
        "key": d["id"],
        "title": d["title"],
        "source_url": d["url"],
        "model": llm.model,
        "generated_at": now_iso(),
    }
    if not d["url"]:
        return {**rec, "status": "no_pdf", "excerpt": None}
    try:
        pdf = fetch_bytes(d["url"])
    except Exception as e:
        return {**rec, "status": "fetch_failed", "excerpt": None, "error": str(e)[:200]}
    try:
        text = extract_text(pdf, max_chars)
    except Exception as e:
        return {
            **rec,
            "status": "extract_failed",
            "excerpt": None,
            "error": "extract: " + str(e)[:180],
        }
    if len(text) < MIN_TEXT_CHARS:
        return {
            **rec,
            "status": "extract_failed",
            "excerpt": None,
            "error": "too little text (scanned or paywalled?)",
        }
    try:
        return {**rec, "status": "ok", "excerpt": summarize(llm, text, d["context"])}
    except Exception as e:
        return {**rec, "status": "llm_failed", "excerpt": None, "error": str(e)[:200]}


def load_cache(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"schema_version": EXCERPT_SCHEMA, "model": None, "generated_at": None, "excerpts": {}}


def save_cache(path, cache):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="llama3.1:70b")
    ap.add_argument("--ollama-url", default="http://localhost:11434")
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--limit", type=int, default=0, help="process at most N new docs (0 = all)")
    ap.add_argument(
        "--retry-failed",
        action="store_true",
        help="also retry docs previously marked no_pdf/failed",
    )
    a = ap.parse_args()

    corpus = json.load(open(a.corpus, encoding="utf-8"))
    cache = load_cache(a.out)
    excerpts = cache["excerpts"]
    llm = LLMClient(a.model, a.ollama_url)

    docs = list(iter_documents(corpus))
    todo = []
    for d in docs:
        prev = excerpts.get(d["id"])
        if prev and prev.get("status") == "ok":
            continue  # already done - cached
        if prev and prev.get("status") == "no_pdf" and not a.retry_failed:
            continue  # no source; skip unless asked
        todo.append(d)
    if a.limit:
        todo = todo[: a.limit]

    print(f"{len(docs)} papers | {len(excerpts)} cached | {len(todo)} to process | model={a.model}")
    ok = failed = 0
    for i, d in enumerate(todo, 1):
        rec = process_one(llm, d, a.max_chars)
        excerpts[d["id"]] = rec
        if rec["status"] == "ok":
            ok += 1
        elif rec["status"] != "no_pdf":
            failed += 1
        if i % 10 == 0 or i == len(todo):
            cache.update(model=a.model, generated_at=now_iso())
            save_cache(a.out, cache)  # checkpoint - a crash won't lose progress
            print(f"  {i}/{len(todo)}  ok={ok} failed={failed}")
        time.sleep(0.2)  # be polite to PDF hosts

    cache.update(model=a.model, generated_at=now_iso())
    save_cache(a.out, cache)
    breakdown = {}
    for r in excerpts.values():
        breakdown[r["status"]] = breakdown.get(r["status"], 0) + 1
    print(f"Done. {len(excerpts)} excerpts total -> {a.out}")
    print(f"  status: {breakdown}")


if __name__ == "__main__":
    main()
