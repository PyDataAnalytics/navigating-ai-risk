# ai-risk-retrieval

Intelligent retrieval of AI risk research papers across a structured taxonomy. Built for reuse: ship the package, point it at your taxonomy, schedule it, and consume the JSON.

## What it does

1. **Expands queries** with an LLM (one cached call per subcategory) so sparse subcategories like "Wireheading" get 4–6 strong query variants instead of one literal string.
2. **Fetches** candidate papers from six sources (arXiv, Semantic Scholar, OpenAlex, Papers With Code, SSRN, Google Scholar via SerpAPI) for each leaf subcategory in your taxonomy.
3. **De-duplicates** across sources using DOI / arXiv ID / normalized title.
4. **Shortlists** the most plausible candidates using citation *velocity* (per-year, not absolute) plus recency and abstract richness.
5. **Screens** an extended shortlist with a cheap LLM (e.g. `llama3.2:3b`) — a binary yes/no relevance gate that lets us sample more papers without raising compute on the expensive judge. *Optional; toggle via `llm_screen.enabled`.*
6. **Judges** survivors with the detailed LLM (e.g. `llama3.1:8b`), which scores relevance 0–10 and writes a one-line rationale. Subcategory `excludes` are passed in to disambiguate names (e.g. "Hallucinations" → LLM hallucinations, NOT medical).
7. **Composes** the final score from LLM relevance, citation velocity, recency, and a source-diversity bonus.
8. **Diversifies** the top-N selection with MMR so three near-duplicate follow-up papers don't sweep the slots — operator gets three meaningfully different perspectives. λ exposed as `scoring.diversity_lambda`.
9. **Outputs** structured JSON consumable by a webapp.

## Why this design

The taxonomy has ~150 leaf subcategories. Manual curation doesn't scale; pure keyword search returns noise. An LLM judge in the loop gets you targeted, defensible selections — provided the judge is treated as an untrusted component.

### Sourcing details
- **Six sources, including OpenAlex** (~250M works, no API key needed) for broad coverage of preprints and non-arXiv venues.
- **LLM query expansion** runs once per `(taxonomy_version, model, subcategory)` and is cached on disk — re-runs against the same taxonomy make zero expansion calls. Expansion is best-effort: failures fall back to the operator's manual keywords.
- **Citation velocity, not absolute citations.** A 2024 paper with 30 cites/year beats a 2015 paper with the same accumulated total. Both the pre-LLM shortlist and the post-LLM composite score use velocity.
- **Two-stage judging.** A cheap screen model filters an extended shortlist (default 50) down to the budget for the detailed judge (default 20). Better recall at the same wall-clock cost on the expensive model. Disable by setting `llm_screen.enabled: false`.
- **Negative anchors.** Each taxonomy entry can declare `excludes: [...]` — phrases that shouldn't match. Threaded into both screen and judge prompts. Especially useful for ambiguous names ("Hallucinations", "Wireheading", "Drone misuse").
- **MMR diversification.** Final pick is greedy MMR over candidates above the min-score floor. λ=1.0 reproduces the original pure-score behavior; λ=0.6 (default) avoids near-duplicate selections while still respecting score. Set per-deployment via `scoring.diversity_lambda`.

## Security posture

Paper abstracts come from the open web. They can contain prompt-injection payloads aimed at the LLM judge. The architecture assumes this and defends against it:

- **LLM is sandboxed**: no tool use, no network access, no file access, no decision power over what gets fetched or stored. It reads sanitized text and emits a score + short rationale.
- **Input sanitization**: control characters stripped, length capped, common injection patterns neutralized (see `evaluator/sanitizer.py`).
- **Strict output parsing**: forced JSON, Pydantic-validated, bounded score range. Malformed output → paper is dropped or re-evaluated, never trusted.
- **Provenance**: every paper retains source URL, fetch timestamp, content hash. Suspicious entries are traceable.
- **No secrets in prompts**: API keys never enter the LLM context; injected text cannot exfiltrate them.
- **Reproducibility**: temperature pinned low, seed configured where supported, full prompts logged for audit.

See `docs/SECURITY.md` for the full threat model.

## Quickstart

```bash
# Install
pip install -e .

# Pull the judge model (one-time)
ollama pull llama3.1:8b

# Configure (copy and edit)
cp config/example.yaml config/local.yaml

# Run for one subcategory (smoke test)
ai-risk-retrieval run --subcategory "Hallucinations" --limit 5

# Run the full taxonomy
ai-risk-retrieval run --all
```

Output lands in `data/output/results-<timestamp>.json`.

## Development workflow

All taxonomy and adjacency invariants are enforced automatically. Three gates, in order:

```bash
# One-time setup — installs pre-commit hooks
make install-dev

# Before every commit (auto-runs via pre-commit, can also run manually):
make validate    # taxonomy drift guard + adjacency integrity (~1s)
make audit       # Layer 1 quality audits (~2s)

# Before pushing — runs exactly what CI runs:
make ci          # validate + audit + full tests + lint
```

### Test architecture — five layers

**Layer 0 — structural integrity (`tests/test_adjacencies.py`, 22 checks)**

Drift guard + adjacency integrity. Runs in <1s. Catches: canonical-name drift, ordering, duplicates, broken refs, self-loops, missing fields, invalid enums, disambiguation/similar shape match.

**Layer 1 — content quality (`tests/test_quality_audits.py`, 6 checks)**

Content-quality audits that complement structural integrity. Each is a hard failure on regression, not a warning:

| Audit | What it catches |
|---|---|
| A2 | Disambiguation median word count drifting below floor in any category (signal of formulaic authoring) |
| A3 | Same line appearing in both `applies_when` and `does_not_apply_when` (copy-paste bug) |
| A5 | Entries with fewer than 3 user_signals (sparse retrieval coverage) |
| A6 | Near-identical one_lines within a similar-cluster (taxonomy itself is the bug — no disambiguation can fix it) |
| A7 | Disambiguation text not referencing the sibling by name (generic / placeholder-like text) |
| A8 | Asymmetric similar edges (A→B in similar but B→A missing — matcher sees inconsistent context) |

**Layer 2 — behavioral evaluation (`tests/test_benchmark.py` + `tests/golden_set/`)**

Golden-set benchmark with a deterministic baseline matcher. The current
golden set has 28 queries; grow to ~200 for real statistical confidence.
Smoke tests ensure the harness runs and that the baseline keyword-overlap
matcher stays above a recall floor.

| Slice | R@1 (baseline) | R@5 | MRR |
|---|---|---|---|
| easy | 1.00 | 1.00 | 1.00 |
| medium | 0.80 | 1.00 | 0.90 |
| hard | 0.60 | 0.60 | 0.62 |
| overall | 0.79 | 0.86 | 0.83 |

This is the floor any real (LLM-based) matcher must beat.

**Layer 3 — pipeline behavior (`tests/test_runner.py`, `test_judge.py`, `test_writer.py`, `test_source_http.py` + 9 pre-existing)**

End-to-end orchestration with mocked sources and judge: filtering, dedup,
shortlisting, threshold-based dropping, target_papers honoring, source failure
isolation, judge output parsing, atomic writes, optional-field stripping,
HTTP resilience (4xx/5xx/timeouts/conn-errors all return `[]`).

**Layer 4 — security (`tests/test_security_e2e.py` + `test_sanitizer.py`)**

End-to-end injection chain: 7 representative payloads (instruction-override,
role-marker, fence-breakout, fake-output, invisible-unicode, base64,
markdown-link) verified to be neutralized at sanitize → fence → parse stages.
Plus pre-existing sanitizer-pattern unit tests.

**Layer 5 — operational (`tests/test_operational.py`)**

Determinism guarantees: dedup, MMR, composite scoring, and full-write JSON
must be byte-identical across runs on identical input. Plus schema-stability
tests: top-level / SubcategoryResult / ScoredPaper output shapes are pinned
and any field-name drift fails CI.

### Enforcement matrix

| Gate | When it runs | Layers enforced |
|---|---|---|
| `pre-commit` hook | every `git commit` | L0 + L1 (fast checks only) |
| GitHub Actions `ci.yml` | every push and PR to `main` | L0 + L1 + L2 + L3 + L4 + L5 + lint |
| `make ci` | manually before pushing | same as CI |

**Total: 182 tests** across 18 files, all green.

### Taxonomy maintenance passes

Pass scripts in `scripts/` are **idempotent** — re-running on an already-processed file is a no-op (verified by SHA256 stability):

```bash
make pass-a    # Type adjacent_to; enforce similar-edge symmetry
make pass-b    # Add disambiguation field (per-similar-edge); auto-derive reverses
make pass-c    # (planned) Tighten applies_when to be discriminative
```

Each pass ends with `make validate` so a broken pass cannot leave the file in a half-migrated state.

### Content vs mechanism split

Disambiguation authoring lives in `scripts/disambiguation_content.py` as `DISAMBIGUATIONS: dict[(source, sibling), str]`. Pass B is the mechanism: it consumes the content module, auto-derives reverse-direction disambiguations via swap-halves for symmetric edges, and writes the YAML. This split means:

- Editing authored content never risks breaking the script
- The script can change without re-authoring content
- The content module is the *sole source of truth* — the YAML is a derived artifact

## Scheduled runs

`.github/workflows/scheduled-retrieval.yml` runs weekly. Results are committed to a `data/` branch or pushed to an artifact store; see the workflow file for options.

## Integrating into a webapp

The output JSON is stable and versioned. Load it from your backend (file, S3, or REST endpoint depending on deployment). Schema is in `src/ai_risk_retrieval/storage/schema.py`.

## License

MIT
