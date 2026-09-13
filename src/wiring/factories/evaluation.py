"""
RAG evaluation composition.

Builds the LLM judge shared by RAGEvaluator (answer_relevancy /
context_precision / context_recall) and by whichever FaithfulnessBackend
is selected, plus the single switch point deciding which
FaithfulnessBackend implementation FaithfulnessMetric and
OnlineEvalSampler both get -- see build_faithfulness_backend.

The resolver is only constructed when the judge is actually invoked,
not eagerly at build time -- callers that never produce a metric
result requiring a judge call (e.g. evaluation cases with no generated
answer) never need a configured LLM provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.dto.inference import LLMInferenceConfig
from core.enums import MessageRoleEnum
from rag.evaluation.evaluator import Judge, RAGEvaluator
from rag.evaluation.faithfulness_backend import (
    FaithfulnessBackend,
    LegacyFaithfulnessBackend,
    RagasFaithfulnessBackend,
)
from wiring.factories.llm_resolver import build_llm_resolver

if TYPE_CHECKING:
    from config.settings import Settings


def build_llm_judge(*, settings: Settings) -> Judge:
    """
    Build a Judge callable backed by the default configured LLM
    provider.
    """

    async def judge(prompt: str) -> str:
        resolver = build_llm_resolver(settings=settings)

        response = await resolver.get().generate(
            request=LLMRequestDTO(
                messages=(
                    LLMMessageDTO(
                        role=MessageRoleEnum.USER,
                        content=prompt,
                    ),
                ),
                # Every caller of this judge (faithfulness, answer
                # relevancy, context precision/recall -- legacy and
                # ragas-backed alike, see ragas_llm_adapter.py) is a
                # scoring call, not a generative one. Previously this
                # request carried no inference config, silently
                # defaulting to LLMInferenceConfig's bare 0.2 -- an
                # ambient, undeliberate temperature for a judge whose
                # output is supposed to be a reproducible score.
                # Pinned to 0.0 (as close to deterministic as providers
                # allow) so repeated judge calls on the same input are
                # stable -- required for the empirical threshold
                # calibration in AnswerQualityPolicy to remain
                # meaningful over time (scripts/
                # calibrate_answer_quality_thresholds.py).
                inference=LLMInferenceConfig(temperature=0.0),
            ),
        )

        return response.content

    return judge


def build_rag_evaluator(*, settings: Settings) -> RAGEvaluator:
    """
    Build a RAGEvaluator backed by the default configured LLM provider.
    """

    return RAGEvaluator(judge=build_llm_judge(settings=settings))


def build_faithfulness_backend(*, settings: Settings) -> FaithfulnessBackend:
    """
    Build the FaithfulnessBackend selected by
    settings.llm.faithfulness_backend.

    This is the single switch point: FaithfulnessMetric and
    OnlineEvalSampler both call this rather than constructing a backend
    or branching on the setting themselves, so changing the setting
    changes behavior for both, by construction.
    """

    judge = build_llm_judge(settings=settings)

    if settings.llm.faithfulness_backend == "ragas":
        return RagasFaithfulnessBackend(judge=judge)

    return LegacyFaithfulnessBackend(evaluator=RAGEvaluator(judge=judge))
