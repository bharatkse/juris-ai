from __future__ import annotations

import asyncio
from pathlib import Path

from config.settings import Settings
from rag.evaluation.datasets.loader import GoldenDatasetLoader
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from runtime.factories.rag import build_rag_pipeline

DATASET_PATH = Path("tests/datasets/rag/evaluation/legal_retrieval_v1.json")
TOP_K = 5


async def main() -> None:
    dataset = GoldenDatasetLoader().load(
        path=DATASET_PATH,
    )

    pipeline = build_rag_pipeline(
        settings=Settings(),
    )

    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=TOP_K),
            PrecisionAtK(k=TOP_K),
            MeanReciprocalRank(),
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
