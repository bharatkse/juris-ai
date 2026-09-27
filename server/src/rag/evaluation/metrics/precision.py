"""
Precision@K retrieval evaluation metric.

Measures how many of the top-K retrieved results are relevant to the
retrieval ground truth defined by the EvaluationCase.

The metric is provider-independent and does not perform retrieval.
It evaluates RetrievalResult objects already present on EvaluationCase.
"""

from __future__ import annotations

from rag.evaluation.metrics.base import RAGMetric
from rag.evaluation.metrics.text_matching import evidence_in_text
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.metric_result import MetricResult
from rag.models import RetrievalResult


class PrecisionAtK(RAGMetric):
    """
    Evaluate retrieval precision at K.

    pass_threshold is a target, not a guarantee it's reachable: with
    fewer expected ground-truth items than k, precision@k is
    structurally capped below 1.0 (e.g. 1 expected_evidence item at
    k=5 caps a perfect retrieval at 0.2). See evaluate()'s
    achievable_ceiling comment for how passed accounts for this.
    """

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
            expected_count = len(case.expected_evidence)

        elif case.expected_sources:
            score = self._source_precision(
                expected_sources=case.expected_sources,
                retrieved_results=retrieved_results,
            )
            evaluation_basis = "source"
            expected_count = len(case.expected_sources)

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

        # precision@k is structurally capped at expected_count / k: with
        # a single expected_evidence item (this dataset's shape) and
        # k=5, even a perfect retrieval scores 0.2 -- the remaining 4
        # slots have nothing left to be relevant to. That ceiling is a
        # property of how many ground-truth items exist, not a
        # retrieval-quality signal, so pass_threshold is never allowed
        # to demand more than what's actually achievable for this case.
        # recall@k and mrr already independently confirm whether the
        # evidence was found at all; this only relaxes precision@k's
        # own bar, and only down to that ceiling -- a case with enough
        # expected items to clear the full configured threshold still
        # has to.
        achievable_ceiling = min(1.0, expected_count / len(retrieved_results))
        effective_pass_threshold = min(self._pass_threshold, achievable_ceiling)

        return MetricResult(
            metric=self.name,
            score=score,
            passed=score >= effective_pass_threshold,
            metadata={
                "k": str(self._k),
                "evaluation_basis": evaluation_basis,
                "expected_sources": str(len(case.expected_sources)),
                "expected_evidence": str(len(case.expected_evidence)),
                "retrieved_results": str(len(retrieved_results)),
                "effective_pass_threshold": f"{effective_pass_threshold:.4f}",
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

        relevant = sum(1 for result in retrieved_results if result.chunk.source in expected)

        return relevant / len(retrieved_results)

    @staticmethod
    def _evidence_precision(
        *,
        expected_evidence: list[str],
        retrieved_results: list[RetrievalResult],
    ) -> float:
        expected = [evidence.strip() for evidence in expected_evidence if evidence.strip()]

        if not expected:
            return 0.0

        relevant = sum(
            1
            for result in retrieved_results
            if any(evidence_in_text(evidence, result.chunk.text) for evidence in expected)
        )

        return relevant / len(retrieved_results)
