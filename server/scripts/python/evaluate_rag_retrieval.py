"""
Golden-dataset retrieval evaluation.

    PYTHONPATH=src poetry run python scripts/python/evaluate_rag_retrieval.py \
        [--mode full|keyword_only|no_rerank] [--min-pass-rate 65] [--summary FILE]

--mode is the retrieval mode every query must run in (default full). A
search that runs in any other mode, e.g. keyword-only because the
embedding model or its cache is unreachable, stops the run with the
underlying error (exit 2): the evaluation never falls back silently.
keyword_only and no_rerank disable the embedding model or the reranker
on purpose to measure the degraded modes.

Exit codes: 0 ok, 1 pass rate below --min-pass-rate, 2 wrong retrieval mode.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from pathlib import Path

from config.settings import Settings
from rag.evaluation.datasets.loader import GoldenDatasetLoader
from rag.evaluation.metrics.faithfulness import FaithfulnessMetric
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.evaluation.retrieval_mode import (
    EVAL_MODES,
    ModeCheckedRetriever,
    RetrievalModeError,
    format_step_summary,
)
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from rag.keyword_store import PostgresKeywordStore
from rag.pgvector_store import PgVectorStore
from rag.reranker import CrossEncoderReranker
from wiring.factories.cache import build_cache
from wiring.factories.evaluation import build_faithfulness_backend
from wiring.factories.rag import build_rag_pipeline

DATASET_PATH = Path("tests/datasets/rag/evaluation/legal_retrieval_gold_v1.json")
TOP_K = 5

EXIT_BELOW_GATE = 1
EXIT_WRONG_MODE = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Golden-dataset retrieval evaluation.")
    parser.add_argument(
        "--mode",
        choices=EVAL_MODES,
        default="full",
        help="Retrieval mode every query must run in (default: full).",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=None,
        help="Fail (exit 1) below this pass rate, in percent. Omit to report only.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Append a Markdown summary to this file (e.g. $GITHUB_STEP_SUMMARY).",
    )
    return parser.parse_args(argv)


async def main(args: argparse.Namespace) -> int:
    settings = Settings()

    dataset = GoldenDatasetLoader().load(
        path=DATASET_PATH,
    )

    # Own cache instance, per settings.security.CACHE_BACKEND (Redis by
    # default). Query embeddings go through it, so an unreachable Redis
    # fails the embedding call: in full mode that stops the run.
    cache = build_cache(settings=settings)

    pipeline = build_rag_pipeline(
        settings=settings,
        cache=cache,
    )

    retriever = ModeCheckedRetriever.build(
        mode=args.mode,
        embedding_provider=pipeline.embedding_provider,
        vector_store=PgVectorStore(),
        keyword_store=PostgresKeywordStore(),
        reranker=CrossEncoderReranker(),
        rrf_k=settings.llm.rag_rrf_k,
    )

    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=TOP_K),
            PrecisionAtK(k=TOP_K),
            MeanReciprocalRank(),
            # NOTE: the golden dataset has no populated `answer` field
            # for any case today, so this always reports "no generated
            # answer" with passed=True (not applicable, not a failure --
            # see faithfulness.py) until the dataset (or this script)
            # produces real answers. score stays 0.0 and is visible in
            # mean_scores, but it does NOT drag down passed_cases/
            # pass_rate. Wired in now so it activates automatically
            # once that gap is closed.
            FaithfulnessMetric(backend=build_faithfulness_backend(settings=settings, cache=cache)),
        ],
    )

    runner = RetrievalEvaluationRunner(
        retriever=retriever,
        evaluator=evaluator,
        top_k=TOP_K,
    )

    try:
        report = await runner.evaluate(
            dataset=dataset,
        )
    except RetrievalModeError as exc:
        print(f"\nERROR: {exc.message}", file=sys.stderr)
        if exc.__cause__ is not None:
            print("Underlying error (first query):", file=sys.stderr)
            traceback.print_exception(exc.__cause__, file=sys.stderr)
        return EXIT_WRONG_MODE

    used = ", ".join(f"{mode} ({count})" for mode, count in retriever.modes_used.items())

    print("\n=== Legal RAG Retrieval Baseline ===")
    print(f"Dataset:       {dataset.name}")
    print(f"Mode:          requested {args.mode}; used {used}")
    print(f"Cases:         {report.case_count}")
    print(f"Passed cases:  {report.passed_cases}")
    print(f"Failed cases:  {report.failed_cases}")
    print(f"Pass rate:     {report.pass_rate:.2%}")

    print("\nMean scores:")
    for metric_name, score in report.mean_scores.items():
        print(f"  {metric_name}: {score:.4f}")

    print("\nPer-case failures:")
    for index, result in enumerate(report.results, start=1):
        if result.passed:
            continue

        print(f"\nCase {index}:")
        for metric in result.metrics:
            if not metric.passed:
                print(f"  {metric.metric}: " f"{metric.score:.4f} " f"metadata={metric.metadata}")

    if args.summary is not None:
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write(
                format_step_summary(
                    mode=args.mode,
                    modes_used=retriever.modes_used,
                    case_count=report.case_count,
                    passed_cases=report.passed_cases,
                    pass_rate=report.pass_rate,
                    mean_scores=report.mean_scores,
                    min_pass_rate=args.min_pass_rate,
                )
            )

    if args.min_pass_rate is not None and report.pass_rate * 100 < args.min_pass_rate:
        print(
            f"\nERROR: pass rate {report.pass_rate:.2%} is below the "
            f"{args.min_pass_rate}% gate ({args.mode}).",
            file=sys.stderr,
        )
        return EXIT_BELOW_GATE

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
