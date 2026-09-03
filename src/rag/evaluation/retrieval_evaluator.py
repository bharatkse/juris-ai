"""
Retrieval evaluation orchestration.

Evaluates the retrieval output of the frozen RAG pipeline using
deterministic retrieval metrics.

This evaluator:

    - does not perform retrieval
    - does not call an LLM
    - does not know about vector stores
    - does not know about keyword stores
    - does not know about rerankers
    - does not modify RetrievalResult objects

It consumes an EvaluationCase containing the actual retrieval results
and delegates metric calculation to the configured retrieval metrics.
"""

from __future__ import annotations

from rag.evaluation.metrics.base import RAGMetric
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.evaluation_result import EvaluationResult


class RetrievalEvaluator:
    """
    Orchestrates deterministic retrieval evaluation metrics.

    The evaluator receives an EvaluationCase whose retrieval_results
    already came from the production RAG retrieval pipeline.

    Metrics are injected so the evaluator remains independent of
    concrete metric implementations.
    """

    def __init__(
        self,
        *,
        metrics: list[RAGMetric],
    ) -> None:
        self._metrics = list(metrics)

    async def evaluate(
        self,
        *,
        case: EvaluationCase,
    ) -> EvaluationResult:
        """
        Evaluate one retrieval case.

        Each configured metric evaluates the same immutable
        EvaluationCase independently.
        """

        metric_results = [await metric.evaluate(case=case) for metric in self._metrics]

        passed = all(metric_result.passed for metric_result in metric_results)

        return EvaluationResult(
            metrics=metric_results,
            passed=passed,
        )
