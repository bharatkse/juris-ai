"""
RAG evaluation metric result models.

These models contain provider-independent evaluation results.
They do not know how the metric was calculated.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricResult:
    """
    Result produced by a single RAG evaluation metric.

    Attributes:
        metric:
            Stable name of the evaluation metric.

        score:
            Normalized metric score.

        passed:
            Whether the score satisfies the configured quality
            threshold.

        metadata:
            Additional metric-specific evaluation metadata.
    """

    metric: str
    score: float
    passed: bool
    metadata: dict[str, str]
