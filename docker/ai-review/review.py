#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate",
)

MODEL = os.getenv(
    "REVIEW_MODEL",
    "qwen3-coder:30b",
)

DIFF_FILE = Path(
    os.getenv(
        "PR_DIFF_FILE",
        "/workspace/pr.diff",
    )
)

ARCHITECTURE_FILE = Path(
    os.getenv(
        "ARCHITECTURE_FILE",
        "/workspace/architecture.md",
    )
)

PROMPT_FILE = Path(
    os.getenv(
        "PROMPT_FILE",
        "/workspace/review_prompt.md",
    )
)

OUTPUT_FILE = Path(
    os.getenv(
        "REVIEW_OUTPUT_FILE",
        "/workspace/review.md",
    )
)

MAX_DIFF_CHARS = int(
    os.getenv(
        "MAX_DIFF_CHARS",
        "120000",
    )
)


def read_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    return path.read_text(encoding="utf-8")


def wait_for_ollama(
    timeout_seconds: int = 300,
) -> None:
    start = time.time()

    while time.time() - start < timeout_seconds:
        try:
            request = urllib.request.Request(
                "http://127.0.0.1:11434/api/tags",
                method="GET",
            )

            with urllib.request.urlopen(
                request,
                timeout=10,
            ):
                return

        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
        ):
            time.sleep(2)

    raise RuntimeError(
        "Ollama did not become ready within " f"{timeout_seconds} seconds."
    )


def call_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
        },
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=1800,
        ) as response:
            raw = response.read().decode("utf-8")

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError("Ollama returned HTTP " f"{exc.code}: {error_body}") from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not connect to Ollama: {exc}") from exc

    result = json.loads(raw)

    if "response" not in result:
        raise RuntimeError(f"Unexpected Ollama response: {result}")

    return result["response"].strip()


def build_prompt(
    review_prompt: str,
    architecture: str,
    diff: str,
) -> str:
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n" "[DIFF TRUNCATED BY REVIEWER]\n"

    return f"""
{review_prompt}

============================================================
JURIS-AI ARCHITECTURE RULES
============================================================

{architecture}

============================================================
PULL REQUEST DIFF
============================================================

{diff}

============================================================
REVIEW INSTRUCTIONS
============================================================

Review the supplied PR diff against the architecture rules.

Only report issues that have concrete evidence in the diff.

Do not invent files, functions, requirements, or behavior.

Do not report:
- formatting problems handled by Ruff
- type errors handled by MyPy
- subjective coding preferences
- hypothetical issues without evidence
- duplicate findings

Prioritize:
1. Correctness
2. Security
3. Authorization
4. Data integrity
5. Transactions
6. Concurrency
7. Async/sync correctness
8. API compatibility
9. Architecture violations
10. Performance
11. Error handling
12. Missing tests

For every finding include:
- severity
- file
- line/range when possible
- problem
- impact
- suggested fix

If there are no actionable issues, explicitly say so.

Return Markdown only.
""".strip()


def main() -> int:
    try:
        print(f"Using model: {MODEL}")
        print("Waiting for Ollama...")

        wait_for_ollama()

        print("Reading PR diff...")
        diff = read_file(DIFF_FILE)

        print("Reading architecture rules...")
        architecture = read_file(ARCHITECTURE_FILE)

        print("Reading review prompt...")
        review_prompt = read_file(PROMPT_FILE)

        print("Building review prompt...")

        prompt = build_prompt(
            review_prompt=review_prompt,
            architecture=architecture,
            diff=diff,
        )

        print("Running local LLM review...")

        review = call_ollama(prompt)

        if not review:
            raise RuntimeError("LLM returned an empty review.")

        OUTPUT_FILE.write_text(
            review,
            encoding="utf-8",
        )

        print(f"Review written to: {OUTPUT_FILE}")

        return 0

    except Exception as exc:
        print(
            f"AI review failed: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
