"""
Output guardrail result shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class GuardrailActionEnum(StrEnum):
    """
    What an output guardrail did to a response.

    Ordered by severity (NONE < FLAGGED < REDACTED < BLOCKED) --
    GuardrailReviewResult.action is the max severity across every
    individual detection, see OutputGuardrailService._overall_action.
    """

    NONE = "none"
    FLAGGED = "flagged"
    REDACTED = "redacted"
    BLOCKED = "blocked"


class PIICategoryEnum(StrEnum):
    """
    The three default-action buckets a PII entity type falls into --
    see PresidioPIIDetector's module docstring for the reasoning
    behind each bucket's default action.
    """

    STRUCTURED_ID = "structured_id"
    CONTACT = "contact"
    NAMED_ENTITY = "named_entity"


_ACTION_SEVERITY: dict[GuardrailActionEnum, int] = {
    GuardrailActionEnum.NONE: 0,
    GuardrailActionEnum.FLAGGED: 1,
    GuardrailActionEnum.REDACTED: 2,
    GuardrailActionEnum.BLOCKED: 3,
}


def max_severity(actions: list[GuardrailActionEnum]) -> GuardrailActionEnum:
    """
    Return the most severe action among ``actions`` (NONE if empty).
    """

    if not actions:
        return GuardrailActionEnum.NONE

    return max(actions, key=lambda action: _ACTION_SEVERITY[action])


@dataclass(frozen=True, slots=True)
class PIIDetection:
    """
    One PII entity Presidio found and the action taken on it.

    Deliberately carries no raw matched text -- only the entity type,
    category, and the decision made about it. This is what is safe to
    log/persist (see application.services.compliance_log's
    no-raw-content rule); the actual substring only ever exists
    transiently inside PresidioPIIDetector while it builds the
    redacted text.
    """

    entity_type: str
    category: PIICategoryEnum
    action: GuardrailActionEnum
    evidence_matched: bool


@dataclass(frozen=True, slots=True)
class HarmfulContentResult:
    """
    Result of the harmful-content judge check.
    """

    harmful: bool
    category: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GuardrailReviewResult:
    """
    Result of reviewing one final response before it leaves the system.

    ``content`` is the response text to actually return -- redacted in
    place when any detection carried a REDACTED action, unchanged
    otherwise. When ``action`` is BLOCKED, ``content`` is meaningless
    (the caller must not use it; a BLOCKED result means the caller
    should regenerate or fall back, never return this content).
    """

    content: str
    action: GuardrailActionEnum
    detections: tuple[PIIDetection, ...] = field(default_factory=tuple)
    harmful: HarmfulContentResult | None = None
