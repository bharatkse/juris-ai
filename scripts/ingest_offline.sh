#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

read -r -p "Enter input path [default: raw_datasets]: " INPUT_PATH
INPUT_PATH="${INPUT_PATH:-raw_datasets}"

if [[ ! -d "$INPUT_PATH" ]]; then
    echo "Error: directory does not exist: $INPUT_PATH" >&2
    exit 1
fi

# Resolve relative paths against the project root.
if [[ "$INPUT_PATH" = /* ]]; then
    SOURCE_DIR="$INPUT_PATH"
else
    SOURCE_DIR="${PROJECT_ROOT}/${INPUT_PATH}"
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Error: directory does not exist: $SOURCE_DIR" >&2
    exit 1
fi

# Create log directory.
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_DIR}/ingest_offline_${TIMESTAMP}.log"

echo "Starting offline ingestion"
echo "Project root : $PROJECT_ROOT"
echo "Input path   : $SOURCE_DIR"
echo "Log file     : $LOG_FILE"
echo

# Capture stdout + stderr while also displaying it in the terminal.
poetry run python -m rag.ingestion.ingest_offline "$SOURCE_DIR" 2>&1 | tee "$LOG_FILE"

EXIT_CODE="${PIPESTATUS[0]}"

echo
echo "Offline ingestion finished with exit code: ${EXIT_CODE}"
echo "Log saved to: ${LOG_FILE}"

exit "$EXIT_CODE"
