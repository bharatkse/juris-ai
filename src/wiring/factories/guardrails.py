"""
Output guardrail service composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentic.guardrails.harmful_content import HarmfulContentJudge
from agentic.guardrails.pii import PresidioPIIDetector
from agentic.guardrails.service import OutputGuardrailService
from wiring.factories.evaluation import build_llm_judge

if TYPE_CHECKING:
    from adapters.cache.base import AbstractCache
    from config.settings import Settings


def create_output_guardrail_service(
    *,
    settings: Settings,
    cache: AbstractCache,
) -> OutputGuardrailService:
    """
    Build the OutputGuardrailService.

    PresidioPIIDetector loads a spaCy model at construction time --
    like clients.embedding_provider/hybrid_retriever, this must happen
    exactly once at process startup (composition.py), never per
    request. The harmful-content judge reuses the same cached,
    temperature=0.0 Judge groundedness/relevance already use (see
    agentic/guardrails/harmful_content.py's docstring).
    """

    return OutputGuardrailService(
        pii_detector=PresidioPIIDetector(
            spacy_model=settings.guardrails.GUARDRAIL_SPACY_MODEL,
        ),
        harmful_content_judge=HarmfulContentJudge(
            judge=build_llm_judge(settings=settings, cache=cache),
        ),
    )
