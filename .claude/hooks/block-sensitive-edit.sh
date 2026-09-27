#!/bin/bash
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

if [[ "$file_path" == *.env* ]] || [[ "$file_path" == *migrations/* ]]; then
  echo "Blocked: edits to .env or migrations/ require manual review." >&2
  exit 2
fi

exit 0
