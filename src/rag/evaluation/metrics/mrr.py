"""
Mean Reciprocal Rank (MRR) retrieval evaluation metric.

Measures the rank of the first relevant result in the retrieved
results.

For a single evaluation case:

    reciprocal_rank = 1 / rank_of_first_relevant_result

MRR is particularly useful for evaluating whether the most relevant
legal evidence appears near the top of the retrieval ranking.

The metric is provider-independent and does not perform retrieval.
"""

from __future__ import annotations

from rag.evaluation.metrics.base import RAGMetric
from rag.evaluation.models import EvaluationCase, MetricResult
from rag.models import RetrievalResult


class MeanReciprocalRank(RAGMetric):
    """Evaluate Mean Reciprocal Rank for a retrieval result set."""

    @property
    def name(self) -> str:
        return "mrr"

    async def evaluate(
        self,
        *,
        case: EvaluationCase,
    ) -> MetricResult:
        if case.expected_evidence:
            rank = self._first_evidence_rank(
                expected_evidence=case.expected_evidence,
                retrieved_results=case.retrieval_results,
            )
            evaluation_basis = "evidence"

        elif case.expected_sources:
            rank = self._first_source_rank(
                expected_sources=case.expected_sources,
                retrieved_results=case.retrieval_results,
            )
            evaluation_basis = "source"

        else:
            return MetricResult(
                metric=self.name,
                score=0.0,
                passed=False,
                metadata={
                    "reason": "missing retrieval ground truth",
                },
            )

        score = 1.0 / rank if rank is not None else 0.0

        return MetricResult(
            metric=self.name,
            score=score,
            passed=score > 0.0,
            metadata={
                "evaluation_basis": evaluation_basis,
                "first_relevant_rank": (str(rank) if rank is not None else "not_found"),
                "retrieved_results": str(len(case.retrieval_results)),
            },
        )

    @staticmethod
    def _first_source_rank(
        *,
        expected_sources: list[str],
        retrieved_results: list[RetrievalResult],
    ) -> int | None:
        expected = {source.strip() for source in expected_sources if source.strip()}

        if not expected:
            return None

        for rank, result in enumerate(retrieved_results, start=1):
            if result.chunk.source_id in expected:
                return rank

        return None

    @staticmethod
    def _first_evidence_rank(
        *,
        expected_evidence: list[str],
        retrieved_results: list[RetrievalResult],
    ) -> int | None:
        expected = [evidence.strip().lower() for evidence in expected_evidence if evidence.strip()]

        if not expected:
            return None

        for rank, result in enumerate(retrieved_results, start=1):
            chunk_text = result.chunk.text.lower()

            if any(evidence in chunk_text for evidence in expected):
                return rank

        return None
