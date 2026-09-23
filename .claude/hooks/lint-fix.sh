#!/bin/bash
# Runs after every Edit/Write/MultiEdit. Fixes lint/format issues on the
# edited file; if anything is still wrong, exit 2 so Claude sees it and fixes it.
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Only lint Python files
[[ "$file_path" == *.py ]] || exit 0
[[ -f "$file_path" ]] || exit 0

RUFF="${CLAUDE_PROJECT_DIR}/.venv/bin/ruff"
if [[ ! -x "$RUFF" ]]; then
  echo "lint-fix hook: ruff not found at $RUFF (run make poetry-install)" >&2
  exit 1   # non-blocking error, shown to the user
fi

# Autofix first so removed imports don't leave gaps the formatter already ran past
"$RUFF" check --fix --quiet "$file_path" >/dev/null 2>&1

if ! format_output=$("$RUFF" format "$file_path" 2>&1); then
  echo "ruff format failed on $file_path:" >&2
  echo "$format_output" >&2
  exit 2
fi

# Re-check after autofix; anything remaining needs Claude's attention
if ! remaining=$("$RUFF" check "$file_path" 2>&1); then
  echo "$remaining" >&2
  exit 2
fi

exit 0
