#!/usr/bin/env bash
# Local-dev-only role separation. Creates (or, if it already exists,
# re-syncs) juris_ai_app: a NOSUPERUSER runtime role the app connects
# as for normal request handling, distinct from the migration/admin
# role (POSTGRES_USER / this project's DB_USER, e.g. juris_ai_user)
# that owns the schema and runs Alembic.
#
# Runs automatically, only the first time this container boots against
# an EMPTY data volume -- docker-entrypoint-initdb.d scripts never
# re-run against an existing volume. That is exactly why this logic is
# idempotent (see _create_app_role.lib) and why
# scripts/bash/setup_app_role.sh exists as a second, developer-run
# entry point for anyone whose local Postgres volume already existed
# before this role-separation work landed -- run that script once
# instead of wiping your volume. Both entry points share the exact
# same SQL (_create_app_role.lib, sourced below), not two versions
# that can drift.
#
# Cloud/RDS role separation is explicitly out of scope -- this script
# is mounted only into the local docker-compose Postgres container
# (docker-compose-localstack.yml's `postgres` service), not any cloud
# provisioning path.
#
# Runs as POSTGRES_USER (the admin/owner role, set by the postgres
# image's own entrypoint before any docker-entrypoint-initdb.d script
# runs) -- CREATE ROLE and ALTER DEFAULT PRIVILEGES both require
# privilege the role being created here must never have.
#
# APP_DB_USER / APP_DB_PASSWORD come from this container's own
# environment (env_file: ../../.env on the postgres service).
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_create_app_role.lib"

ADMIN_ROLE="$POSTGRES_USER"
DB_NAME="$POSTGRES_DB"
export ADMIN_ROLE DB_NAME APP_DB_USER APP_DB_PASSWORD

create_app_role_sql | psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"
