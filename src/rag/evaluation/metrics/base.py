"""
Base contract for RAG evaluation metrics.

Metric implementations consume an EvaluationCase and return a
MetricResult.

The contract is intentionally independent of:

    - LLM providers
    - embedding providers
    - SQLAlchemy
    - vector stores
    - Ragas
    - concrete evaluation frameworks
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.metric_result import MetricResult


class RAGMetric(ABC):
    """
    Base contract for a RAG evaluation metric.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the stable metric name.
        """

        raise NotImplementedError

    @abstractmethod
    async def evaluate(
        self,
        *,
        case: EvaluationCase,
    ) -> MetricResult:
        """
        Evaluate a RAG response.

        Args:
            case:
                Provider-independent RAG evaluation input.

        Returns:
            Metric result.
        """

        raise NotImplementedError
