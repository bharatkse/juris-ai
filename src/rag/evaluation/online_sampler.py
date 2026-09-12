"""
Online evaluation sampler.

Runs RAGEvaluator against a configurable fraction of real production
requests, asynchronously, after the response has already been
returned to the user — evaluation must never add latency to the
request path. Results are logged/emitted as metrics for dashboards
and alerting, not used to block or alter the response itself.

For rigorous, ground-truth-backed evaluation, use
rag/evaluation/ragas_offline.py against a curated eval set instead —
this sampler only computes the three metrics that don't need a
ground-truth answer (faithfulness, answer_relevancy,
context_precision).
"""

from __future__ import annotations

import random

from adapters.observability.logger import get_logger
from adapters.observability.telemetry import get_meter
from rag.evaluation.evaluator import RAGEvaluator

log = get_logger(__name__)

DEFAULT_SAMPLE_RATE = 0.05  # evaluate 5% of requests — tune based on local LLM headroom


class OnlineEvalSampler:
    """
    Fire-and-forget evaluation on a sample of production traffic.
    """

    def __init__(
        self,
        *,
        evaluator: RAGEvaluator,
        sample_rate: float = DEFAULT_SAMPLE_RATE,
    ) -> None:
        self._evaluator = evaluator
        self._sample_rate = sample_rate

        meter = get_meter("juris-agentic.rag_evaluation")

        self._faithfulness_histogram = meter.create_histogram(
            name="rag_faithfulness",
            description="Sampled RAG faithfulness score (LLM-as-judge).",
            unit="1",
        )
        self._answer_relevancy_histogram = meter.create_histogram(
            name="rag_answer_relevancy",
            description="Sampled RAG answer relevancy score (LLM-as-judge).",
            unit="1",
        )
        self._context_precision_histogram = meter.create_histogram(
            name="rag_context_precision",
            description="Sampled RAG context precision score (LLM-as-judge).",
            unit="1",
        )

    def should_sample(self) -> bool:
        return random.random() < self._sample_rate

    async def evaluate_and_record(
        self,
        *,
        question: str,
        answer: str,
        retrieved_chunks: list[str],
        request_id: str,
    ) -> None:
        """
        Call this from a background task (e.g. asyncio.create_task),
        never awaited inline on the request path.
        """

        try:
            result = await self._evaluator.evaluate(
                question=question,
                answer=answer,
                retrieved_chunks=retrieved_chunks,
            )

        except Exception:
            log.exception("Online RAG evaluation failed for request_id=%s.", request_id)
            return

        tags = {"request_id": request_id}
        if result.faithfulness is not None:
            self._faithfulness_histogram.record(result.faithfulness, attributes=tags)
        if result.answer_relevancy is not None:
            self._answer_relevancy_histogram.record(result.answer_relevancy, attributes=tags)
        if result.context_precision is not None:
            self._context_precision_histogram.record(result.context_precision, attributes=tags)

        if result.has_quality_concern():
            log.warning(
                "RAG quality concern for request_id=%s: faithfulness=%s "
                "relevancy=%s precision=%s.",
                request_id,
                result.faithfulness,
                result.answer_relevancy,
                result.context_precision,
            )
