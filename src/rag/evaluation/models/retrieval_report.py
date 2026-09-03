"""
Dataset-level retrieval evaluation report.

Aggregates per-case retrieval evaluation results into a single report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from rag.evaluation.models.evaluation_result import EvaluationResult


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationReport:
    """
    Aggregated retrieval evaluation results for a golden dataset.
    """

    results: list[EvaluationResult] = field(default_factory=list)

    @property
    def case_count(self) -> int:
        return len(self.results)

    @property
    def passed_cases(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def failed_cases(self) -> int:
        return self.case_count - self.passed_cases

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return self.passed_cases / self.case_count

    @property
    def mean_scores(self) -> dict[str, float]:
        scores: dict[str, list[float]] = {}

        for result in self.results:
            for metric, score in result.scores.items():
                scores.setdefault(metric, []).append(score)

        return {metric: mean(metric_scores) for metric, metric_scores in scores.items()}

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)
