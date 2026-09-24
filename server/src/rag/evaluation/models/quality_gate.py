"""
Retrieval evaluation quality gates.

Provides threshold-based validation for an existing
RetrievalEvaluationReport.

This module does not:
    - execute retrieval
    - execute evaluation
    - modify evaluation results
    - change the RAG workflow
    - call an LLM
    - access persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport


@dataclass(frozen=True, slots=True)
class QualityGateResult:
    """Result of evaluating retrieval quality gates."""

    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RetrievalQualityGate:
    """
    Validate aggregated retrieval metrics against configured thresholds.

    Thresholds are applied to the dataset-level mean scores.
    """

    thresholds: dict[str, float]

    def __post_init__(self) -> None:
        for metric, threshold in self.thresholds.items():
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(f"Threshold for '{metric}' must be between 0.0 and 1.0.")

    def evaluate(
        self,
        *,
        report: RetrievalEvaluationReport,
    ) -> QualityGateResult:
        """Evaluate all configured metric thresholds."""

        scores = report.mean_scores
        failures: list[str] = []

        for metric, threshold in self.thresholds.items():
            score = scores.get(metric)

            if score is None:
                failures.append(f"{metric}: metric result is missing")
                continue

            if score < threshold:
                failures.append(f"{metric}: {score:.4f} < required {threshold:.4f}")

        return QualityGateResult(
            passed=not failures,
            failures=failures,
        )
