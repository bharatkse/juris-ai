from __future__ import annotations

import asyncio
from pathlib import Path

from config.settings import Settings
from rag.evaluation.datasets.loader import GoldenDatasetLoader
from rag.evaluation.metrics.faithfulness import FaithfulnessMetric
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from wiring.factories.cache import build_cache
from wiring.factories.evaluation import build_faithfulness_backend
from wiring.factories.rag import build_rag_pipeline

DATASET_PATH = Path("tests/datasets/rag/evaluation/legal_retrieval_gold_v1.json")
TOP_K = 5


async def main() -> None:
    settings = Settings()

    dataset = GoldenDatasetLoader().load(
        path=DATASET_PATH,
    )

    # Own cache instance -- Redis-backed by default (settings.security.
    # CACHE_BACKEND), so repeated script runs across separate processes
    # also hit cache for embeddings/judge calls on unchanged inputs.
    cache = build_cache(settings=settings)

    pipeline = build_rag_pipeline(
        settings=settings,
        cache=cache,
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
        retriever=pipeline.hybrid_retriever,
        evaluator=evaluator,
        top_k=TOP_K,
    )

    report = await runner.evaluate(
        dataset=dataset,
    )

    print("\n=== Legal RAG Retrieval Baseline ===")
    print(f"Dataset:       {dataset.name}")
    print(f"Cases:         {report.case_count}")
    print(f"Passed cases:  {report.passed_cases}")
    print(f"Failed cases:  {report.failed_cases}")
    print(f"Pass rate:     {report.pass_rate:.2%}")

    print("\nMean scores:")
    for metric, score in report.mean_scores.items():
        print(f"  {metric}: {score:.4f}")

    print("\nPer-case failures:")
    for index, result in enumerate(report.results, start=1):
        if result.passed:
            continue

        print(f"\nCase {index}:")
        for metric in result.metrics:
            if not metric.passed:
                print(f"  {metric.metric}: " f"{metric.score:.4f} " f"metadata={metric.metadata}")


if __name__ == "__main__":
    asyncio.run(main())
