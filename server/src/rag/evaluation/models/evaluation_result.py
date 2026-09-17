"""
RAG evaluation result models.

Contains the aggregate result of evaluating a single RAG response.

This model is independent of the evaluation implementation. It can
represent results produced by online evaluation, offline evaluation,
or any future evaluation strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag.evaluation.models.metric_result import MetricResult


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """
    Aggregate result for a RAG evaluation case.

    Attributes:
        metrics:
            Individual metric results produced during evaluation.

        passed:
            Overall evaluation status.

        metadata:
            Additional evaluation-level metadata.
    """

    metrics: list[MetricResult] = field(default_factory=list)
    passed: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def scores(self) -> dict[str, float]:
        """
        Return metric scores keyed by metric name.
        """

        return {metric.metric: metric.score for metric in self.metrics}
