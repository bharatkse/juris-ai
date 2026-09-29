#!/usr/bin/env bash
# Run one read-only SQL query against the local dev database, as the
# restricted runtime role (APP_DB_USER, e.g. juris_ai_app).
#
# Usage: make db-query SQL="select count(*) from users"
#
# This is allowlisted for Claude Code (.claude/settings.json), so nobody
# reviews the SQL before it runs. The read-only guarantee therefore can't
# rest on PGOPTIONS alone, which the SQL itself could undo:
# - `BEGIN READ WRITE` opens a writable transaction despite
#   default_transaction_read_only=on (reproduced), and
# - psql meta-commands pass straight through -c: `\! id` ran a shell as
#   root inside the Postgres container (reproduced).
# So the query is refused before it reaches psql if it contains any
# backslash (no meta-commands at all) or a statement that controls
# transactions/settings or has effects outside a table write (see
# FORBIDDEN below), and it then runs in a single transaction that starts
# read-only. Refusals are conservative: a keyword inside a string literal
# is refused too. Anything refused here -- writes, role-specific checks,
# admin queries -- stays an explicit `docker exec ... psql` call, which
# goes through the normal permission prompt.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-juris_ai_postgres}"

sql="${1:-}"
if [[ -z "${sql//[[:space:]]/}" ]]; then
    echo 'usage: make db-query SQL="select ..."' >&2
    exit 2
fi

if [[ "$sql" == *\\* ]]; then
    echo "db-query: refused: backslash (psql meta-commands such as \\! or \\copy aren't allowed)" >&2
    exit 2
fi

FORBIDDEN='begin|start[[:space:]]+transaction|commit|rollback|abort|savepoint|release|set|reset|discard|do|call|copy|prepare|execute|deallocate|listen|notify|unlisten|lock|vacuum|cluster|reindex|checkpoint|load|lo_import|lo_export|pg_read_file|pg_read_binary_file|pg_ls_dir|pg_stat_file|dblink[a-z_]*|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_sleep[a-z_]*|set_config'
if match="$(grep -o -i -w -E "$FORBIDDEN" <<<"$sql" | head -n1)"; then
    echo "db-query: refused: '$match' isn't allowed in a read-only query; use an explicit docker exec psql call" >&2
    exit 2
fi

# Same key extraction as setup_app_role.sh: .env isn't guaranteed to be
# valid bash, so only the needed keys are read.
for key in DB_NAME APP_DB_USER; do
    line="$(grep -E "^${key}=" "$REPO_ROOT/.env" | tail -n1)"
    if [[ -n "$line" ]]; then
        export "${line?}"
    fi
done
: "${DB_NAME:?DB_NAME must be set in .env}"
: "${APP_DB_USER:?APP_DB_USER must be set in .env -- see env.example}"

exec docker exec \
    -e PGOPTIONS='-c default_transaction_read_only=on' \
    "$POSTGRES_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 --single-transaction \
    --username "$APP_DB_USER" --dbname "$DB_NAME" \
    -c "$sql"
