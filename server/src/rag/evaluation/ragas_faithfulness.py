"""
Shared ragas-backed faithfulness scoring.

FaithfulnessMetric (offline/golden-dataset evaluation) and
OnlineEvalSampler (production sampling) both need a faithfulness score
computed the same way -- this is the single definition both call,
rather than each independently wrapping ragas' Faithfulness metric.

ragas' own imports are deferred into the functions that actually need
them (matching ragas_offline.py's existing lazy-import pattern) --
importing this module alone must not import ragas or start its
analytics thread; only actually building/using a RagasFaithfulnessBackend
should.
"""

from __future__ import annotations

import math
import typing as t

from rag.evaluation.evaluator import Judge
from rag.evaluation.ragas_llm_adapter import build_judge_ragas_llm

if t.TYPE_CHECKING:
    from ragas.metrics import Faithfulness as RagasFaithfulness


def build_ragas_faithfulness_metric(*, judge: Judge) -> RagasFaithfulness:
    """Build a ragas Faithfulness metric backed by our Judge callable."""

    from ragas.metrics import Faithfulness as RagasFaithfulness

    return RagasFaithfulness(llm=build_judge_ragas_llm(judge=judge))


async def score_faithfulness(
    *,
    ragas_metric: RagasFaithfulness,
    question: str,
    answer: str,
    contexts: list[str],
) -> float | None:
    """
    Score faithfulness via ragas.

    Returns None on any failure -- a judge exception, a malformed
    response ragas couldn't parse after its own retries, or ragas' own
    "no statements were generated from the answer" NaN -- so each
    caller applies its own fallback semantics rather than this
    function guessing what "unavailable" should mean for it.
    """

    from ragas.dataset_schema import SingleTurnSample

    try:
        score = await ragas_metric.single_turn_ascore(
            SingleTurnSample(
                user_input=question,
                response=answer,
                retrieved_contexts=list(contexts),
            ),
        )
    except Exception:
        return None

    if score is None or math.isnan(score):
        return None

    return float(score)
