"""
RAG evaluation domain models.

These models represent evaluation results produced by the RAG
evaluation pipeline.

They are independent of:

    - LLM providers
    - RAGAS
    - persistence
    - retrieval implementations
    - application services
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RAGEvalResult:
    """
    Evaluation result for a single RAG response.

    Metrics:

        faithfulness:
            Whether the generated answer is supported by the
            retrieved context.

        answer_relevancy:
            Whether the generated answer directly addresses the
            user's question.

        context_precision:
            Whether the retrieved context is relevant to the
            question.

        context_recall:
            Whether the retrieved context contains the information
            required to answer the question.

    context_recall is optional because production requests normally
    do not have a ground-truth answer.
    """

    faithfulness: float | None
    answer_relevancy: float | None
    context_precision: float | None
    context_recall: float | None

    def has_quality_concern(
        self,
        *,
        threshold: float = 0.6,
    ) -> bool:
        """
        Return True when any computed metric is below the threshold.

        Metrics that are unavailable (None) are ignored.
        """

        scores = [
            score
            for score in (
                self.faithfulness,
                self.answer_relevancy,
                self.context_precision,
            )
            if score is not None
        ]

        return any(score < threshold for score in scores)
