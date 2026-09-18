#!/usr/bin/env bash
# Pull the locally-configured Ollama model into the running Ollama
# container -- idempotent, safe to run any time.
#
# Why this exists: docker-compose-llm.yml's `ollama` service starts
# the Ollama server with no models baked in (the upstream image ships
# empty) -- LLM_LOCAL_MODEL (env.example, config/llm.py) was never
# actually pulled by anything in the default `make dev`/`make
# restart-hard` flow, so a fresh checkout's local-model path
# (LLM_LOCAL=ollama) silently had no model to serve until someone
# remembered to run `make llm-pull` by hand.
#
# Idempotent -- checks `ollama list` inside the container first and
# skips the (multi-GB) pull entirely if the configured model is
# already present. Deliberately NOT wired into plain `docker compose
# up`/`docker-up` -- only into the explicit setup/bootstrap targets
# (`make dev`, `make restart-hard`) that already run
# scripts/bash/setup_app_role.sh the same way, so a routine restart
# never blocks on a multi-GB download.
#
# Usage: scripts/bash/pull_ollama_models.sh
# Requires: the local Ollama container running (`make llm-up`), and
# LLM_LOCAL_MODEL set in .env (see env.example; falls back to
# qwen3:8b, config/llm.py's LLMSettings.LLM_LOCAL_MODEL default, if
# unset or .env doesn't exist).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OLLAMA_CONTAINER="${OLLAMA_CONTAINER:-juris_ai_ollama}"

# Same reasoning as setup_app_role.sh: read only the one key this
# script needs from .env directly, rather than sourcing it wholesale
# (this project's .env has unquoted values with spaces that aren't
# valid bash).
if [[ -f "$REPO_ROOT/.env" ]]; then
    line="$(grep -E '^LLM_LOCAL_MODEL=' "$REPO_ROOT/.env" | tail -n1)"
    if [[ -n "$line" ]]; then
        export "${line?}"
    fi
fi

# Matches config/llm.py's LLMSettings.LLM_LOCAL_MODEL default
# (LLMMODELEnum.QWEN3_8B) -- kept in sync manually, same as
# setup_app_role.sh's DB_* fallbacks.
LLM_LOCAL_MODEL="${LLM_LOCAL_MODEL:-qwen3:8b}"

if ! docker inspect "$OLLAMA_CONTAINER" >/dev/null 2>&1; then
    echo "error: container '$OLLAMA_CONTAINER' not found. Start it first: make llm-up" >&2
    exit 1
fi

echo "Waiting for Ollama to be ready in '$OLLAMA_CONTAINER'..."
ready=false
for _ in $(seq 1 30); do
    if docker exec "$OLLAMA_CONTAINER" ollama list >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 2
done

if [[ "$ready" != true ]]; then
    echo "error: Ollama in '$OLLAMA_CONTAINER' never became ready." >&2
    exit 1
fi

if docker exec "$OLLAMA_CONTAINER" ollama list | awk 'NR>1 {print $1}' | grep -qx "$LLM_LOCAL_MODEL"; then
    echo "Model '$LLM_LOCAL_MODEL' already present in '$OLLAMA_CONTAINER' -- skipping pull."
else
    echo "Pulling model '$LLM_LOCAL_MODEL' into '$OLLAMA_CONTAINER' (this can take a while)..."
    docker exec "$OLLAMA_CONTAINER" ollama pull "$LLM_LOCAL_MODEL"
    echo "Done. '$LLM_LOCAL_MODEL' is ready."
fi
