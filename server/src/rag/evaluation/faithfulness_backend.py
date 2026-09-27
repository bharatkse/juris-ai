"""
Faithfulness backend switch point.

FaithfulnessBackend is the one interface both FaithfulnessMetric and
OnlineEvalSampler depend on for a faithfulness score. Neither caller
constructs an implementation or branches on configuration itself --
wiring.factories.evaluation.build_faithfulness_backend is the single
place that decision is made, driven by
settings.llm.faithfulness_backend.
"""

from __future__ import annotations

from typing import Protocol

from rag.evaluation.evaluator import Judge, RAGEvaluator
from rag.evaluation.ragas_faithfulness import build_ragas_faithfulness_metric, score_faithfulness


class FaithfulnessBackend(Protocol):
    """Capability contract: score how grounded an answer is in its context."""

    async def evaluate(
        self,
        *,
        query: str,
        answer: str,
        contexts: list[str],
    ) -> float | None:
        """
        Return a faithfulness score in [0.0, 1.0], or None if
        evaluation was not possible (e.g. a malformed judge response).
        """
        ...


class LegacyFaithfulnessBackend:
    """
    Wraps RAGEvaluator's hand-rolled faithfulness judge
    (evaluator.py's faithfulness() / _FAITHFULNESS_PROMPT).

    query is accepted for FaithfulnessBackend-interface compatibility
    but unused -- the legacy judge was never designed to take the
    question into account, only context and answer.
    """

    def __init__(self, *, evaluator: RAGEvaluator) -> None:
        self._evaluator = evaluator

    async def evaluate(
        self,
        *,
        query: str,
        answer: str,
        contexts: list[str],
    ) -> float | None:
        return await self._evaluator.faithfulness(
            context="\n\n".join(contexts),
            answer=answer,
        )


class RagasFaithfulnessBackend:
    """Wraps ragas' own Faithfulness metric (see ragas_faithfulness.py)."""

    def __init__(self, *, judge: Judge) -> None:
        self._ragas_metric = build_ragas_faithfulness_metric(judge=judge)

    async def evaluate(
        self,
        *,
        query: str,
        answer: str,
        contexts: list[str],
    ) -> float | None:
        return await score_faithfulness(
            ragas_metric=self._ragas_metric,
            question=query,
            answer=answer,
            contexts=contexts,
        )
