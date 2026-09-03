"""
Precision@K retrieval evaluation metric.

Measures how many of the top-K retrieved results are relevant to the
retrieval ground truth defined by the EvaluationCase.

The metric is provider-independent and does not perform retrieval.
It evaluates RetrievalResult objects already present on EvaluationCase.
"""

from __future__ import annotations

from rag.evaluation.metrics.base import RAGMetric
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.metric_result import MetricResult
from rag.models import RetrievalResult


class PrecisionAtK(RAGMetric):
    """Evaluate retrieval precision at K."""

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
        return f"precision@{self._k}"

    async def evaluate(
        self,
        *,
        case: EvaluationCase,
    ) -> MetricResult:
        retrieved_results = case.retrieval_results[: self._k]

        if not retrieved_results:
            return MetricResult(
                metric=self.name,
                score=0.0,
                passed=False,
                metadata={
                    "k": str(self._k),
                    "reason": "no retrieval results",
                },
            )

        if case.expected_evidence:
            score = self._evidence_precision(
                expected_evidence=case.expected_evidence,
                retrieved_results=retrieved_results,
            )
            evaluation_basis = "evidence"

        elif case.expected_sources:
            score = self._source_precision(
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
    def _source_precision(
        *,
        expected_sources: list[str],
        retrieved_results: list[RetrievalResult],
    ) -> float:
        expected = {source.strip() for source in expected_sources if source.strip()}

        if not expected:
            return 0.0

        relevant = sum(1 for result in retrieved_results if result.chunk.source_id in expected)

        return relevant / len(retrieved_results)

    @staticmethod
    def _evidence_precision(
        *,
        expected_evidence: list[str],
        retrieved_results: list[RetrievalResult],
    ) -> float:
        expected = [evidence.strip().lower() for evidence in expected_evidence if evidence.strip()]

        if not expected:
            return 0.0

        relevant = sum(
            1
            for result in retrieved_results
            if any(evidence in result.chunk.text.lower() for evidence in expected)
        )

        return relevant / len(retrieved_results)
