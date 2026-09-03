"""
Recall@K retrieval evaluation metric.

Measures whether the expected retrieval evidence is present in the
top-K results produced by the RAG retrieval pipeline.

The metric is provider-independent and does not perform retrieval.
It evaluates RetrievalResult objects already present on EvaluationCase.
"""

from __future__ import annotations

from rag.evaluation.metrics.base import RAGMetric
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.metric_result import MetricResult
from rag.models import RetrievalResult


class RecallAtK(RAGMetric):
    """Evaluate retrieval recall at K."""

    def __init__(
        self,
        *,
        k: int = 5,
        pass_threshold: float = 0.6,
    ) -> None:
        if k <= 0:
            raise ValueError("k must be greater than zero.")

        if not 0.0 <= pass_threshold <= 1.0:
            raise ValueError("pass_threshold must be between 0.0 and 1.0.")

        self._k = k
        self._pass_threshold = pass_threshold

    @property
    def name(self) -> str:
        return f"recall@{self._k}"

    async def evaluate(
        self,
        *,
        case: EvaluationCase,
    ) -> MetricResult:
        retrieved_results = case.retrieval_results[: self._k]

        if case.expected_evidence:
            score = self._evidence_recall(
                expected_evidence=case.expected_evidence,
                retrieved_results=retrieved_results,
            )
            evaluation_basis = "evidence"

        elif case.expected_sources:
            score = self._source_recall(
                expected_sources=case.expected_sources,
                retrieved_results=retrieved_results,
            )
            evaluation_basis = "source"

        else:
            return MetricResult(
                metric=self.name,
                score=0.0,
                passed=False,
                metadata={
                    "k": str(self._k),
                    "reason": "missing retrieval ground truth",
                },
            )

        return MetricResult(
            metric=self.name,
            score=score,
            passed=score >= self._pass_threshold,
            metadata={
                "k": str(self._k),
                "evaluation_basis": evaluation_basis,
                "expected_sources": str(len(case.expected_sources)),
                "expected_evidence": str(len(case.expected_evidence)),
                "retrieved_results": str(len(retrieved_results)),
            },
        )

    @staticmethod
    def _source_recall(
        *,
        expected_sources: list[str],
        retrieved_results: list[RetrievalResult],
    ) -> float:
        expected = {source.strip() for source in expected_sources if source.strip()}

        if not expected:
            return 0.0

        retrieved = {
            result.chunk.source_id for result in retrieved_results if result.chunk.source_id
        }

        return len(expected & retrieved) / len(expected)

    @staticmethod
    def _evidence_recall(
        *,
        expected_evidence: list[str],
        retrieved_results: list[RetrievalResult],
    ) -> float:
        expected = [evidence.strip().lower() for evidence in expected_evidence if evidence.strip()]

        if not expected:
            return 0.0

        retrieved_text = [result.chunk.text.lower() for result in retrieved_results]

        matched = sum(
            1
            for evidence in expected
            if any(evidence in chunk_text for chunk_text in retrieved_text)
        )

        return matched / len(expected)
