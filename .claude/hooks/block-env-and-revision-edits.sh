#!/bin/bash
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Only generated Alembic revisions are blocked; migrations/env.py (e.g.
# _EXTERNALLY_MANAGED_TABLES) is meant to be edited by hand.
if [[ "$file_path" == *.env* ]] || [[ "$file_path" == *migrations/versions/* ]]; then
  echo "Blocked: edits to .env or migrations/versions/ require manual review (generate revisions with make alembic-revision)." >&2
  exit 2
fi

exit 0
