#!/usr/bin/env bash
# Create (or re-sync) the local-dev restricted runtime role
# (APP_DB_USER, e.g. juris_ai_app) against an already-running Postgres
# container -- regardless of when its data volume was created.
#
# Why this exists: ../docker/server/init/postgres/01-create-app-role.sh
# only runs automatically via docker-entrypoint-initdb.d, which
# Postgres only executes the first time a container boots against an
# EMPTY data volume. Anyone with a pre-existing local Postgres volume
# (from before this role-separation work landed, or from any earlier
# `docker compose up`) never gets APP_DB_USER created, and nothing
# tells them why the app then fails to connect. Run this script once
# instead of wiping your volume (`make docker-clean`) just to pick up
# a role.
#
# Idempotent -- safe to run again any time (e.g. after rotating
# APP_DB_PASSWORD in .env, or just to confirm current state). Shares
# its actual SQL with the docker-entrypoint-initdb.d hook via
# ../docker/server/init/postgres/_create_app_role.lib -- one source of
# truth, not two versions that can drift.
#
# Usage: scripts/bash/setup_app_role.sh
# Requires: the local Postgres container running (`make docker-up`),
# and DB_USER/DB_PASSWORD/DB_NAME/APP_DB_USER/APP_DB_PASSWORD set in
# .env (see env.example).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-juris_ai_postgres}"

# shellcheck source=/dev/null
source "$REPO_ROOT/../docker/server/init/postgres/_create_app_role.lib"

if [[ ! -f "$REPO_ROOT/.env" ]]; then
    echo "error: $REPO_ROOT/.env not found. Copy env.example to .env and fill it in first." >&2
    exit 1
fi

# Host-side equivalent of the container hook's POSTGRES_USER/POSTGRES_DB
# env vars: read directly from .env rather than the running
# container's own environment, since a long-running Postgres container
# started BEFORE .env last changed won't have picked up a new
# APP_DB_USER/APP_DB_PASSWORD either -- exactly the same staleness
# this script exists to work around for the app container.
#
# Deliberately NOT `source .env` wholesale: this project's .env uses
# plain KEY=value lines that are valid for pydantic-settings but not
# necessarily valid bash (e.g. APP_NAME=Legal AI Assistant -- an
# unquoted value containing spaces, which bash would try to word-split
# and run as a command). Extracting only the specific keys this script
# needs, each expected to be a single bash-safe token, sidesteps that
# entirely rather than requiring every .env value project-wide to stay
# shell-safe.
for key in DB_USER DB_NAME APP_DB_USER APP_DB_PASSWORD; do
    line="$(grep -E "^${key}=" "$REPO_ROOT/.env" | tail -n1)"
    if [[ -n "$line" ]]; then
        export "${line?}"
    fi
done

: "${DB_USER:?DB_USER must be set in .env}"
: "${DB_NAME:?DB_NAME must be set in .env}"
: "${APP_DB_USER:?APP_DB_USER must be set in .env -- see env.example}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set in .env -- see env.example}"

if ! docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1; then
    echo "error: container '$POSTGRES_CONTAINER' not found. Start it first: make docker-up" >&2
    exit 1
fi

ADMIN_ROLE="$DB_USER"
export ADMIN_ROLE DB_NAME APP_DB_USER APP_DB_PASSWORD

echo "Creating/syncing role '$APP_DB_USER' in database '$DB_NAME' (container: $POSTGRES_CONTAINER)..."

create_app_role_sql | docker exec -i "$POSTGRES_CONTAINER" \
    psql -v ON_ERROR_STOP=1 --username "$DB_USER" --dbname "$DB_NAME"

echo "Done. '$APP_DB_USER' is ready."
