#!/usr/bin/env bash
# pod_discovery.sh - runs ON a freshly-created RunPod pod (over SSH).
#
# The discovery workflow now CREATES A FRESH POD each run, so this script
# bootstraps everything from a bare image (nothing persists between runs):
#   1. ensure git / curl / Ollama are installed
#   2. start Ollama (no systemd in the container) and pull the judge+screen models
#   3. clone the repo into the ephemeral /workspace
#   4. pip install the package (editable)
#   5. run the full retrieval, leaving data/output/latest.json on disk
#
# Network steps are wrapped in retry() so a transient apt/pip/pull/clone hiccup
# self-heals instead of failing the weekly run. The workflow scp's latest.json
# back and merges it into the corpus on the runner; this script never touches
# git history or corpus state - it only produces a run.
#
# Tunables (env, all defaulted):
#   WORKDIR   repo location on the pod
#   REPO_URL  public clone URL
#   CONFIG    pipeline config (Ollama localhost; llama3.1:8b judge + llama3.2:3b screen)
#   JUDGE_MODEL / SCREEN_MODEL   Ollama tags to ensure present
#   OLLAMA_VERSION         pin the Ollama binary version (reproducible installs)
#   OLLAMA_INSTALL_SHA256  pin the installer script (see note below)
# Optional source creds forwarded by the workflow: SEMANTIC_SCHOLAR_API_KEY,
# OPENALEX_MAILTO, UNPAYWALL_EMAIL, SERPAPI_API_KEY.
set -euo pipefail
WORKDIR="${WORKDIR:-/workspace/ai-risk-retrieval-work/navigating-ai-risk}"
REPO_URL="${REPO_URL:-https://github.com/PyDataAnalytics/navigating-ai-risk.git}"
CONFIG="${CONFIG:-config/ci.yaml}"
JUDGE_MODEL="${JUDGE_MODEL:-llama3.1:8b}"
SCREEN_MODEL="${SCREEN_MODEL:-llama3.2:3b}"
# Pin the Ollama installer + version.
#  - After the FIRST run, copy the "ollama install.sh sha256=..." value printed
#    in the discovery log into OLLAMA_INSTALL_SHA256 below; from then on a changed
#    installer fails the run loudly instead of executing silently.
#  - OLLAMA_VERSION pins the binary version (recommended; leave empty = latest).
OLLAMA_VERSION="${OLLAMA_VERSION:-}"
OLLAMA_INSTALL_SHA256="${OLLAMA_INSTALL_SHA256:-}"
# retry <cmd...> : up to 3 attempts with backoff (10s, 20s)
retry() {
  local n=1
  until "$@"; do
    if [ "$n" -ge 3 ]; then
      echo "::pod:: giving up after $n attempts: $*" >&2
      return 1
    fi
    echo "::pod:: attempt $n failed, retrying: $*" >&2
    sleep $((n * 10))
    n=$((n + 1))
  done
}
echo "::pod:: ensuring base tooling (git, curl, zstd, ollama)"
need_apt=0
for tool in git curl zstd; do
  command -v "$tool" >/dev/null 2>&1 || need_apt=1
done
if [ "$need_apt" = "1" ]; then
  retry apt-get update
  # zstd is required by the current Ollama installer to unpack its release.
  retry apt-get install -y --no-install-recommends git curl ca-certificates zstd
fi
# Hardened Ollama install: download the installer to a file (NOT `curl | sh`),
# print + verify its sha256, then run it with the version pinned. This removes
# blind execution of a remote script and makes the install reproducible.
if ! command -v ollama >/dev/null 2>&1; then
  retry curl -fsSL https://ollama.com/install.sh -o /tmp/ollama_install.sh
  observed="$(sha256sum /tmp/ollama_install.sh | cut -d' ' -f1)"
  echo "::pod:: ollama install.sh sha256=${observed}"
  if [ -n "${OLLAMA_INSTALL_SHA256}" ]; then
    if [ "${observed}" != "${OLLAMA_INSTALL_SHA256}" ]; then
      echo "::pod:: install.sh checksum mismatch (expected ${OLLAMA_INSTALL_SHA256}); refusing to run installer" >&2
      exit 1
    fi
  else
    echo "::pod:: WARNING: OLLAMA_INSTALL_SHA256 not set - installer NOT verified. Pin it to the sha above." >&2
  fi
  OLLAMA_VERSION="${OLLAMA_VERSION}" sh /tmp/ollama_install.sh
  rm -f /tmp/ollama_install.sh
fi
echo "::pod:: starting Ollama if needed"
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  for _ in $(seq 1 60); do
    curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || { echo "Ollama not reachable"; exit 1; }
echo "::pod:: ensuring models present"
ollama list | grep -q "${JUDGE_MODEL}"  || retry ollama pull "${JUDGE_MODEL}"
ollama list | grep -q "${SCREEN_MODEL}" || retry ollama pull "${SCREEN_MODEL}"
echo "::pod:: syncing repo at ${WORKDIR}"
if [ -d "${WORKDIR}/.git" ]; then
  retry git -C "${WORKDIR}" fetch --depth 1 origin main
  git -C "${WORKDIR}" reset --hard origin/main
else
  mkdir -p "$(dirname "${WORKDIR}")"
  retry git clone --depth 1 "${REPO_URL}" "${WORKDIR}"
fi
cd "${WORKDIR}"
echo "::pod:: ensuring package installed"
command -v ai-risk-retrieval >/dev/null 2>&1 || retry pip install -e . -q
echo "::pod:: validating config"
ai-risk-retrieval validate-config -c "${CONFIG}" -t config/taxonomy.yaml
echo "::pod:: running full retrieval"
ai-risk-retrieval run --all -c "${CONFIG}" -t config/taxonomy.yaml
LATEST="${WORKDIR}/data/output/latest.json"
test -f "${LATEST}" || { echo "expected ${LATEST} not found"; exit 1; }
echo "::pod:: done -> ${LATEST}"
