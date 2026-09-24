"""
Golden dataset models for RAG evaluation.

A golden dataset contains evaluation cases with expected answers
and/or expected relevant contexts.

The dataset is independent of the evaluation implementation and does
not depend on any concrete LLM or evaluation framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag.evaluation.models.evaluation_case import EvaluationCase


@dataclass(frozen=True, slots=True)
class GoldenDataset:
    """
    Collection of RAG evaluation cases used as ground truth.

    Attributes:
        name:
            Stable identifier for the evaluation dataset.

        cases:
            Evaluation cases containing expected answers and/or
            expected retrieval contexts.

        metadata:
            Dataset-level metadata such as version or description.
    """

    name: str
    cases: list[EvaluationCase] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def size(self) -> int:
        """
        Return the number of evaluation cases.
        """

        return len(self.cases)
