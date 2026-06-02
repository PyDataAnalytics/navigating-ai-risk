#!/usr/bin/env bash
# pod_discovery.sh — runs ON the RunPod pod (over SSH) to produce a fresh run.
#
# Idempotent bootstrap so a freshly-resumed pod is always in a known-good state:
#   1. start Ollama if it isn't already serving (no systemd in the container)
#   2. ensure the judge + screen models are pulled
#   3. clone the repo on first run, otherwise fast-forward it
#   4. install the package (editable) if the console script is missing
#   5. run the full retrieval; leave data/output/latest.json on disk
#
# The workflow then scp's latest.json back and merges it into the corpus on the
# runner. This script never pushes git or handles corpus state — it only produces
# a run. Tunables come in as environment variables (all have sane defaults):
#
#   WORKDIR    where the repo lives on the /workspace volume (survives Stop)
#   REPO_URL   public clone URL (only used on first run)
#   CONFIG     pipeline config (Ollama localhost; llama3.1:8b judge + llama3.2:3b screen)
#   JUDGE_MODEL / SCREEN_MODEL   Ollama tags to ensure present
# Plus optional source creds forwarded by the workflow: SEMANTIC_SCHOLAR_API_KEY,
# OPENALEX_MAILTO, UNPAYWALL_EMAIL, SERPAPI_API_KEY.

set -euo pipefail

WORKDIR="${WORKDIR:-/workspace/ai-risk-retrieval-work/navigating-ai-risk}"
REPO_URL="${REPO_URL:-https://github.com/PyDataAnalytics/navigating-ai-risk.git}"
CONFIG="${CONFIG:-config/ci.yaml}"
JUDGE_MODEL="${JUDGE_MODEL:-llama3.1:8b}"
SCREEN_MODEL="${SCREEN_MODEL:-llama3.2:3b}"

echo "::pod:: starting Ollama if needed"
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || { echo "Ollama not reachable"; exit 1; }

echo "::pod:: ensuring models present"
ollama list | grep -q "${JUDGE_MODEL}"  || ollama pull "${JUDGE_MODEL}"
ollama list | grep -q "${SCREEN_MODEL}" || ollama pull "${SCREEN_MODEL}"

echo "::pod:: syncing repo at ${WORKDIR}"
if [ -d "${WORKDIR}/.git" ]; then
  git -C "${WORKDIR}" fetch --depth 1 origin main
  git -C "${WORKDIR}" reset --hard origin/main
else
  mkdir -p "$(dirname "${WORKDIR}")"
  git clone --depth 1 "${REPO_URL}" "${WORKDIR}"
fi
cd "${WORKDIR}"

echo "::pod:: ensuring package installed"
command -v ai-risk-retrieval >/dev/null 2>&1 || pip install -e . -q

echo "::pod:: validating config"
ai-risk-retrieval validate-config -c "${CONFIG}" -t config/taxonomy.yaml

echo "::pod:: running full retrieval"
ai-risk-retrieval run --all -c "${CONFIG}" -t config/taxonomy.yaml

LATEST="${WORKDIR}/data/output/latest.json"
test -f "${LATEST}" || { echo "expected ${LATEST} not found"; exit 1; }
echo "::pod:: done -> ${LATEST}"
