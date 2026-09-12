"""
Faithfulness RAG evaluation metric.

Measures whether the generated answer's claims are actually supported
by the retrieved context -- i.e. whether the answer is grounded in
evidence rather than hallucinated.

Unlike mrr.py / precision.py / recall.py, faithfulness cannot be
computed as a retrieval-ground-truth heuristic (expected_evidence /
expected_sources vs. retrieved_results): it depends on the semantic
relationship between the *generated answer* and the *retrieved
context*, which requires a judge capable of natural-language
entailment. There is exactly one definition of that judgment in this
codebase -- RAGEvaluator.faithfulness() in evaluator.py, including its
prompt -- and this metric wraps it rather than re-deriving a second,
inconsistent definition of "faithfulness".

This makes FaithfulnessMetric the only metric in this package that
requires an LLM call (via an injected RAGEvaluator) and the only one
that evaluates case.answer / case.contexts rather than
case.expected_evidence / case.expected_sources. It still conforms to
the RAGMetric contract so it runs interchangeably with the
retrieval-only metrics through retrieval_evaluator.py.
"""

from __future__ import annotations

from rag.evaluation.evaluator import RAGEvaluator
from rag.evaluation.metrics.base import RAGMetric
from rag.evaluation.models import EvaluationCase, MetricResult


class FaithfulnessMetric(RAGMetric):
    """Evaluate whether the generated answer is grounded in retrieved context."""

    def __init__(
        self,
        *,
        evaluator: RAGEvaluator,
        pass_threshold: float = 0.6,
    ) -> None:
        if not 0.0 <= pass_threshold <= 1.0:
            raise ValueError("pass_threshold must be between 0.0 and 1.0.")

        self._evaluator = evaluator
        self._pass_threshold = pass_threshold

    @property
    def name(self) -> str:
        return "faithfulness"

    async def evaluate(
        self,
        *,
        case: EvaluationCase,
    ) -> MetricResult:
        contexts = case.contexts

        if not contexts:
            return MetricResult(
                metric=self.name,
                score=0.0,
                passed=False,
                metadata={
                    "reason": "no retrieved context",
                },
            )

        if not case.answer.strip():
            # Not applicable, not a failure: this case simply has no
            # generated answer to judge (e.g. a retrieval-only golden
            # dataset that never populates `answer`). Reporting
            # passed=True here keeps an unrelated data gap from
            # dragging down the aggregate pass/fail rollup for every
            # other metric on this case -- the "reason" in metadata is
            # what tells a reader this metric didn't actually run.
            return MetricResult(
                metric=self.name,
                score=0.0,
                passed=True,
                metadata={
                    "reason": "no generated answer",
                },
            )

        score = await self._evaluator.faithfulness(
            context="\n\n".join(contexts),
            answer=case.answer,
        )

        if score is None:
            return MetricResult(
                metric=self.name,
                score=0.0,
                passed=False,
                metadata={
                    "reason": "judge evaluation unavailable",
                },
            )

        return MetricResult(
            metric=self.name,
            score=score,
            passed=score >= self._pass_threshold,
            metadata={
                "retrieved_results": str(len(contexts)),
            },
        )
