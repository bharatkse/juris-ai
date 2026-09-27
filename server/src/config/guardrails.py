from __future__ import annotations

from config.base import BaseAppSettings


class GuardrailSettings(BaseAppSettings):
    """
    Output guardrail (PII redaction / harmful-content) configuration.
    """

    # Small spaCy model, not the default en_core_web_lg -- see
    # agentic/guardrails/pii.py's module docstring for why. Overridable
    # per-deployment (e.g. a larger model) without a code change.
    GUARDRAIL_SPACY_MODEL: str = "en_core_web_sm"

    # Bounded regenerate-on-block loop for harmful content (see
    # AIOrchestrator.handle()): the first attempt plus this many
    # regenerate attempts before falling back to a fixed refusal.
    # Mirrors the existing bounded-retry pattern in
    # AgentContinuationService._gate_final -- never unbounded.
    GUARDRAIL_MAX_REGENERATE_ATTEMPTS: int = 1
