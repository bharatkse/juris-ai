from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config.settings import Settings
from rag.embeddings import SentenceTransformerEmbeddingProvider
from rag.evaluation.datasets.loader import GoldenDatasetLoader
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.evaluation_result import EvaluationResult
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.hybrid_retriever import HybridRetriever
from rag.keyword_store import PostgresKeywordStore
from rag.pgvector_store import PgVectorStore
from rag.reranker import CrossEncoderReranker

DATASET_PATH = "tests/datasets/rag/evaluation/legal_retrieval_v1.json"
TOP_K = 5


@dataclass(frozen=True, slots=True)
class RetrieverResult:
    name: str
    evaluation: EvaluationResult


async def evaluate_retriever(
    *,
    name: str,
    retriever,
    dataset,
    evaluator: RetrievalEvaluator,
) -> RetrieverResult:
    metric_results = []

    for case in dataset.cases:
        retrieval_results = await retriever.retrieve(
            query=case.query,
            top_k=TOP_K,
        )

        evaluated_case = EvaluationCase(
            query=case.query,
            answer=case.answer,
            retrieval_results=retrieval_results,
            reference_answer=case.reference_answer,
            reference_contexts=case.reference_contexts,
            expected_sources=case.expected_sources,
            expected_evidence=case.expected_evidence,
        )

        result = await evaluator.evaluate(case=evaluated_case)
        metric_results.append(result)

    from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport

    report = RetrievalEvaluationReport(results=metric_results)

    print(f"\n=== {name} ===")
    print(f"Cases:        {report.case_count}")
    print(f"Passed:       {report.passed_cases}")
    print(f"Failed:       {report.failed_cases}")
    print(f"Pass rate:    {report.pass_rate:.4f}")

    for metric, score in sorted(report.mean_scores.items()):
        print(f"{metric:<15} {score:.4f}")

    return RetrieverResult(
        name=name,
        evaluation=EvaluationResult(
            metrics=[],
            passed=report.passed,
            metadata={
                "case_count": str(report.case_count),
            },
        ),
    )


async def main() -> None:
    settings = Settings()

    dataset = GoldenDatasetLoader().load(
        path=DATASET_PATH,
    )

    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=TOP_K),
            PrecisionAtK(k=TOP_K),
            MeanReciprocalRank(),
        ],
    )

    # One embedding provider shared by Vector and Hybrid retrieval.
    embedding_provider = SentenceTransformerEmbeddingProvider()

    vector_store = PgVectorStore()
    keyword_store = PostgresKeywordStore()
    reranker = CrossEncoderReranker()

    hybrid_retriever = HybridRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        keyword_store=keyword_store,
        reranker=reranker,
        rrf_k=settings.llm.rag_min_rerank_score,
    )

    await evaluate_retriever(
        name="Hybrid",
        retriever=hybrid_retriever,
        dataset=dataset,
        evaluator=evaluator,
    )

    print("\nComparison requires direct Vector/Keyword interfaces.")
    print("Current production KeywordStore exposes query(),")
    print("while VectorStore exposes query() rather than retrieve().")


if __name__ == "__main__":
    asyncio.run(main())
