"""
RAG evaluation composition.

Builds a RAGEvaluator whose judge calls the application's configured
LLM resolver, for use as the LLM-judge dependency of FaithfulnessMetric
(and any other LLM-judge metric added later).

The resolver is only constructed when the judge is actually invoked,
not eagerly at build time -- callers that never produce a metric
result requiring a judge call (e.g. evaluation cases with no generated
answer) never need a configured LLM provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.enums import MessageRoleEnum
from rag.evaluation.evaluator import RAGEvaluator
from wiring.factories.llm_resolver import build_llm_resolver

if TYPE_CHECKING:
    from config.settings import Settings


def build_rag_evaluator(*, settings: Settings) -> RAGEvaluator:
    """
    Build a RAGEvaluator backed by the default configured LLM provider.
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
            ),
        )

        return response.content

    return RAGEvaluator(judge=judge)
