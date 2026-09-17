#!/usr/bin/env bash
# Install and start Juris AI from the published release images.
#
# What this does: generates real random secrets into .env (SECRET_KEY,
# JWT_SECRET_KEY, DB_PASSWORD, APP_DB_PASSWORD), prompts for the one
# value that can't be generated (GROQ_API_KEY), brings up
# postgres/redis/searxng/api via docker-compose.yml, runs the DB
# migrations, and polls the real health endpoint until the API is
# actually serving traffic -- not just "container started".
#
# For developing on the backend itself (running from source, tests,
# linting), see server/CONTRIBUTING.md instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NON_INTERACTIVE=false
for arg in "$@"; do
  case "$arg" in
    --non-interactive) NON_INTERACTIVE=true ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--non-interactive]" >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required but not found on PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "error: 'docker compose' (v2 plugin) is required but not available." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Creating .env from env.example..."
  cp env.example .env
fi

# Generates a URL-safe random secret and substitutes it into .env, but
# only if the key still holds its CHANGE_ME placeholder -- re-running
# install.sh must not rotate secrets on an existing install.
generate_secret_if_placeholder() {
  local key="$1"
  local current
  current="$(grep -E "^${key}=" .env | head -n1 | cut -d= -f2-)"
  if [[ "$current" == "CHANGE_ME" || -z "$current" ]]; then
    local value
    value="$(openssl rand -hex 32)"
    sed -i.bak "s|^${key}=.*|${key}=${value}|" .env
    rm -f .env.bak
    echo "  Generated ${key}."
  fi
}

echo "Generating secrets (skipping any already set)..."
generate_secret_if_placeholder "SECRET_KEY"
generate_secret_if_placeholder "JWT_SECRET_KEY"
generate_secret_if_placeholder "DB_PASSWORD"
generate_secret_if_placeholder "APP_DB_PASSWORD"

# GROQ_API_KEY is the one value nothing can generate -- it's the only
# thing this script ever prompts for.
current_groq="$(grep -E '^GROQ_API_KEY=' .env | head -n1 | cut -d= -f2-)"
if [[ -z "$current_groq" ]]; then
  if [[ -n "${GROQ_API_KEY:-}" ]]; then
    sed -i.bak "s|^GROQ_API_KEY=.*|GROQ_API_KEY=${GROQ_API_KEY}|" .env
    rm -f .env.bak
  elif [[ "$NON_INTERACTIVE" == false ]]; then
    echo ""
    echo "Juris AI needs a Groq API key for LLM inference (https://console.groq.com/keys)."
    read -r -p "Enter your GROQ_API_KEY (leave blank to add it to .env later): " groq_key
    if [[ -n "$groq_key" ]]; then
      sed -i.bak "s|^GROQ_API_KEY=.*|GROQ_API_KEY=${groq_key}|" .env
      rm -f .env.bak
    fi
  else
    echo "warning: GROQ_API_KEY not set and --non-interactive given -- chat requests will fail until it's added to .env." >&2
  fi
fi

echo ""
echo "Pulling images..."
docker compose pull

echo "Starting services..."
docker compose up -d

echo "Waiting for postgres to become healthy..."
for _ in $(seq 1 30); do
  status="$(docker compose ps --format json postgres 2>/dev/null | grep -o '"Health":"[a-z]*"' | cut -d'"' -f4 || true)"
  [[ "$status" == "healthy" ]] && break
  sleep 2
done

echo "Running database migrations..."
docker compose exec -T api alembic upgrade head

API_PORT="$(grep -E '^API_PORT=' .env | head -n1 | cut -d= -f2- || true)"
API_PORT="${API_PORT:-8001}"

echo "Waiting for the API to report healthy at http://localhost:${API_PORT}/api/v1/health..."
ready=false
for _ in $(seq 1 60); do
  if curl -sf "http://localhost:${API_PORT}/api/v1/health" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done

if [[ "$ready" != true ]]; then
  echo "error: API did not become healthy in time. Check logs with: docker compose logs api" >&2
  exit 1
fi

echo ""
echo "Juris AI is running."
echo "  Swagger UI: http://localhost:${API_PORT}/docs"
echo "  ReDoc:      http://localhost:${API_PORT}/redoc"
echo "  Health:     http://localhost:${API_PORT}/api/v1/health"
