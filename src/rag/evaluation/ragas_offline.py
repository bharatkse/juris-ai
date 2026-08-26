"""
Offline RAG evaluation — ragas-based, for CI/regression testing.

Run this against a curated golden dataset (question, ground_truth,
retrieved contexts, generated answer) whenever the retrieval pipeline
changes — new embedding model, new chunk size, reranker swap, prompt
changes. This is what catches "we made retrieval worse" before it
ships, which online sampling alone (metrics.py + online_sampler.py)
cannot, since online sampling has no ground truth to compare against.

Uses the `ragas` library rather than the hand-rolled LLM-judge in
metrics.py — ragas' metric implementations are more thoroughly
validated and worth the extra dependency + cost for an offline,
infrequent CI job (not per-request).

Usage:
    poetry run python -m src.rag.evaluation.ragas_offline \
        --dataset eval/golden_dataset.jsonl

Golden dataset format (JSONL, one record per line):
    {"question": "...", "ground_truth": "...", "contexts": ["...", "..."], "answer": "..."}
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

log = get_logger(__name__)

# Minimum acceptable scores — CI fails the build if the mean falls
# below these. Tune based on your golden dataset's difficulty; these
# are reasonable starting points, not universal thresholds.
QUALITY_GATES = {
    "faithfulness": 0.75,
    "answer_relevancy": 0.75,
    "context_precision": 0.6,
    "context_recall": 0.6,
}

# Column normalization map: canonical ragas schema <- input dataset schema
_COLUMN_MAPPING = {
    "question": "user_input",
    "answer": "response",
    "contexts": "retrieved_contexts",
    "ground_truth": "reference",
}


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        log.error("Dataset file not found: %s", file_path)
        sys.exit(1)

    records: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                row = json.loads(line_str)
                # Normalize column keys to standard Ragas dataset requirements
                normalized = {_COLUMN_MAPPING.get(k, k): v for k, v in row.items()}
                # Ensure retrieved_contexts is always a list
                if isinstance(normalized.get("retrieved_contexts"), str):
                    normalized["retrieved_contexts"] = [normalized["retrieved_contexts"]]
                records.append(normalized)
            except json.JSONDecodeError:
                log.warning("Skipping invalid JSON on line %d in %s", line_num, file_path)

    return records


def run_ragas_evaluation(records: list[dict[str, Any]]) -> dict[str, float]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError:
        log.error("ragas or datasets not installed — install via: pip install ragas datasets")
        sys.exit(1)

    dataset = Dataset.from_list(records)

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    # Extract means safely across dataset evaluations
    scores: dict[str, float] = {}
    try:
        df = result.to_pandas()
        for metric in QUALITY_GATES:
            # Check for direct or alias column names
            matching_cols = [c for c in df.columns if metric in c.lower()]
            if matching_cols:
                scores[metric] = float(df[matching_cols[0]].mean())
    except Exception:
        # Fallback to direct dict conversion
        scores = {k: float(v) for k, v in dict(result).items() if v is not None}

    return scores


def check_quality_gates(scores: dict[str, float]) -> bool:
    passed = True

    for metric, threshold in QUALITY_GATES.items():
        score = scores.get(metric)

        if score is None or math.isnan(score):
            log.error("Quality gate FAILED: metric '%s' missing or evaluated to NaN.", metric)
            passed = False
            continue

        if score < threshold:
            log.error(
                "Quality gate FAILED: %s = %.3f (threshold %.3f).",
                metric,
                score,
                threshold,
            )
            passed = False
        else:
            log.info("Quality gate passed: %s = %.3f.", metric, score)

    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline RAG evaluation via ragas.")
    parser.add_argument("--dataset", required=True, help="Path to golden dataset JSONL.")
    args = parser.parse_args()

    records = load_dataset(args.dataset)

    if not records:
        log.error("Dataset '%s' is empty or contains no valid rows.", args.dataset)
        sys.exit(1)

    log.info("Running ragas evaluation over %d record(s).", len(records))

    scores = run_ragas_evaluation(records)
    passed = check_quality_gates(scores)

    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
