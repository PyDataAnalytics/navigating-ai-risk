# Security & Threat Model

This document captures how `ai-risk-retrieval` defends itself, what threats it
addresses, and what it explicitly does not.

## 1. Threat model

**Assets**
- The output JSON (consumed by webapps; downstream code may render it).
- The LLM judge (local Ollama instance).
- Any API keys present in the runtime environment (SerpAPI, Semantic Scholar).

**Adversaries**
1. *Paper authors gaming retrieval.* Most realistic. An author with a weak
   paper inserts text into their abstract/title hoping to elevate it in
   automated curation systems.
2. *Compromised source endpoint.* arXiv proxies, mirror hosts, or upstream
   APIs returning manipulated content.
3. *Compromised dependency.* A malicious package update to one of our deps
   (defended by lockfile + verified PyPI; not in scope for code here).
4. *Operator misconfiguration.* Pointing the judge at an untrusted Ollama
   instance shared with other workloads.

**Out of scope**
- The webapp consuming our output is responsible for its own rendering
  security (e.g., escaping `rationale` when displayed as HTML). We strip
  obvious HTML in `LLMJudgement` as defense in depth, but webapps still
  must treat all string fields as untrusted.
- DoS via volume of papers; rate limits and per-source caps mitigate but
  don't eliminate.

## 2. Defenses by layer

### Layer 1: Source fetching
- **Bounded budgets**: each source has a per-subcategory candidate cap.
- **Strict schemas**: every paper passes through Pydantic with regex validation
  on DOI and arXiv ID (URL-injection vectors disabled — only `http(s)://`).
- **Field length caps** on title, abstract, authors prevent any one paper
  from monopolizing memory or downstream prompts.
- **Control-character stripping** on every API field.
- **HTTPS only** for all source APIs.
- **No follow-arbitrary-link**: we don't fetch URLs *referenced inside*
  papers, only the bibliographic URL the source returned.

### Layer 2: Pre-LLM
- Candidates merged and deduplicated. Source priority determines which
  metadata wins on conflicts, preventing a malicious source from poisoning
  citation counts on a paper that another source already indexed.

### Layer 3: LLM judge (the high-value target)
The judge is the most attractive injection target. Defenses:

| Defense                                   | What it stops |
|-------------------------------------------|---------------|
| Localhost-only Ollama host (config check) | Exfiltration to remote LLM provider |
| Sanitization before prompt insertion      | Most known injection patterns |
| Unicode tag/format char stripping         | "Invisible" instruction smuggling |
| NFKC normalization                        | Lookalike char attacks |
| Hard prompt fence around paper text       | Naive context-break attempts |
| Explicit "data, not instructions" framing | Trained injection resistance |
| `format=json` in Ollama call              | Free-form response that smuggles output |
| Pydantic schema validation of output      | Out-of-range scores, oversized rationale |
| Bounded score range [0, 10]               | Compromised model returning 999 |
| HTML stripping on rationale               | XSS via downstream rendering |
| No tools / no network / no files for LLM  | LLM cannot act on injected instructions |
| Audit log of every call (hashed)          | Forensic traceability |

When the two-stage screener is enabled, all of the above defenses apply
identically to the screen call. The screen output is a single boolean,
strictly validated; a compromised screen model can at worst (a) leak a
paper that should have been filtered into the detailed judge — which then
scores it on the same rubric and discards it if irrelevant, or (b) filter
out a paper that should have passed — which degrades recall but doesn't
compromise the output. Both failure modes are recoverable; neither lets
the attacker control the final output.

### Layer 4: Output
- Atomic writes prevent partial-file reads.
- Schema-versioned JSON. Consumers can pin to a version and detect changes.
- No raw HTML in any output field.

## 3. What an attacker still can do

- **Score inflation by topical match.** An attacker can write a genuinely
  relevant abstract. The LLM will score it accordingly. This is correct
  behavior, not a vulnerability — the system is designed to surface relevant
  papers regardless of who wrote them.
- **Force a low score on their own paper** with a clumsy injection that
  trips the neutralization layer. The system prompt explicitly instructs
  the model to score down attempts at manipulation. Net effect: the
  injection backfires.
- **Saturate one source.** Bounded per-source caps and source-diversity
  bonus mitigate; a determined attacker dominating multiple sources
  would still need real-looking metadata.

## 4. Operational guidance

- Run Ollama as a non-privileged user. Bind to `127.0.0.1` only (the config
  enforces this by default; do not override without understanding the risk).
- Do not run on a multi-tenant machine where another user can submit
  inference requests to the same Ollama instance.
- Audit `data/cache/audit.jsonl` periodically. Look for suspiciously high
  scores from unusual sources, repeated content hashes (someone re-publishing
  the same content under different IDs), or LLM parse failures clustered
  around one source (potential coordinated attack).
- Rotate API keys (`SEMANTIC_SCHOLAR_API_KEY`, `SERPAPI_API_KEY`) yearly.
- Pin dependencies via lockfile in your deployment.

### RunPod credentials (discovery workflow)

`RUNPOD_API_KEY` is the highest-value secret here: it can start and stop GPU pods,
which costs money. Treat it accordingly — use a dedicated key for CI, set a RunPod
billing alert, and rotate it on a schedule. `RUNPOD_SSH_KEY` is a private SSH key
scoped to one pod; generate a fresh keypair for CI rather than reusing a personal
key, and remove its public half from the pod if you retire the automation. Both
are encrypted Actions secrets and, because `discovery` runs only on `schedule` and
`workflow_dispatch`, are never exposed to pull requests. The discovery job's
`Stop pod` step runs with `if: always()`, so a crashed or cancelled run cannot
leave a GPU billing indefinitely.

### Secrets in a public repository

This repo is public, but its credentials live in **GitHub Actions secrets**, which
are encrypted at rest and masked in logs. They are safe here because:

- Both data workflows (`weekly-refresh`, `discovery`) trigger only on `schedule`
  and `workflow_dispatch` — never on `pull_request`. Pull requests from forks
  therefore have no path to read the secrets (the classic public-repo leak vector).
- No secret is ever written to the corpus, the site data, or a commit. The
  refresh/discovery scripts read keys from the environment only.
- Every key is optional. The weekly refresh runs (key-less S2 + OpenAlex paths)
  even with no secrets configured; keys only raise rate limits / enable Unpaywall.

The durable `corpus.json` and the abstract-stripped `snapshots/` committed here
contain **metadata only** (titles, authors, DOIs, citation counts, OA link URLs)
— no paper full text and no abstracts. See `merge_corpus.py` for the strip step.

### Weekly-refresh job safety

`scripts/refresh_corpus.py` is hardened against corrupting the historical asset:
it validates before writing (paper count must stay constant, `first_seen` is
immutable, no abstract may appear, the corpus must round-trip through JSON) and
writes atomically (temp file + `os.replace`). A failed validation aborts the
write with a non-zero exit and leaves the committed corpus untouched.

## 5. Reporting issues

If you find a security vulnerability, please open a private security advisory
on GitHub rather than a public issue.
