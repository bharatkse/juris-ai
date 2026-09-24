"""
Unit tests for OutputGuardrailService.

pii_detector/harmful_content_judge are mocked here -- their real
behavior is covered by test_pii.py/test_harmful_content.py; these
tests are about the service's own orchestration logic (short-circuit
on harmful, severity aggregation, content selection).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.guardrails.schemas import (
    GuardrailActionEnum,
    HarmfulContentResult,
    PIICategoryEnum,
    PIIDetection,
)
from agentic.guardrails.service import OutputGuardrailService


def _service(*, harmful: bool, pii_detections: tuple[PIIDetection, ...] = ()):
    pii_detector = MagicMock()
    pii_detector.review = MagicMock(
        return_value=("redacted content" if pii_detections else "original content", pii_detections),
    )

    harmful_content_judge = MagicMock()
    harmful_content_judge.evaluate = AsyncMock(
        return_value=HarmfulContentResult(
            harmful=harmful, category="violence" if harmful else None
        ),
    )

    return (
        OutputGuardrailService(
            pii_detector=pii_detector,
            harmful_content_judge=harmful_content_judge,
        ),
        pii_detector,
        harmful_content_judge,
    )


@pytest.mark.asyncio
async def test_harmful_content_short_circuits_pii_review() -> None:
    """
    A harmful verdict returns BLOCKED without ever calling the PII
    detector -- there is nothing useful to redact in content the
    caller must discard/regenerate.
    """

    service, pii_detector, _judge = _service(harmful=True)

    result = await service.review(content="anything")

    assert result.action is GuardrailActionEnum.BLOCKED
    assert result.harmful is not None
    assert result.harmful.harmful is True
    pii_detector.review.assert_not_called()


@pytest.mark.asyncio
async def test_no_detections_returns_none_action_and_original_content() -> None:
    service, _detector, _judge = _service(harmful=False, pii_detections=())

    result = await service.review(content="original content")

    assert result.action is GuardrailActionEnum.NONE
    assert result.content == "original content"


@pytest.mark.asyncio
async def test_overall_action_is_the_max_severity_across_detections() -> None:
    """
    A FLAGGED detection alongside a REDACTED one must report REDACTED
    overall (REDACTED > FLAGGED in severity) -- the caller (orchestrator)
    only branches on the single overall action, not per-detection.
    """

    detections = (
        PIIDetection(
            entity_type="PERSON",
            category=PIICategoryEnum.NAMED_ENTITY,
            action=GuardrailActionEnum.FLAGGED,
            evidence_matched=True,
        ),
        PIIDetection(
            entity_type="IN_PAN",
            category=PIICategoryEnum.STRUCTURED_ID,
            action=GuardrailActionEnum.REDACTED,
            evidence_matched=False,
        ),
    )

    service, _detector, _judge = _service(harmful=False, pii_detections=detections)

    result = await service.review(content="original content")

    assert result.action is GuardrailActionEnum.REDACTED
    assert result.content == "redacted content"
    assert len(result.detections) == 2


@pytest.mark.asyncio
async def test_evidence_text_is_passed_through_to_the_pii_detector() -> None:
    service, pii_detector, _judge = _service(harmful=False)

    await service.review(content="content", evidence_text="some evidence")

    pii_detector.review.assert_called_once_with(
        text="content",
        evidence_text="some evidence",
    )


@pytest.mark.asyncio
async def test_failing_judge_call_blocks_the_response() -> None:
    """
    End-to-end through the real judge: a judge LLM call that raises must
    produce BLOCKED, and PII review is skipped (nothing to redact in a
    response that won't be shown).
    """

    from agentic.guardrails.harmful_content import HarmfulContentJudge

    async def failing_judge(prompt: str) -> str:
        raise TimeoutError("judge timed out")

    pii_detector = MagicMock()
    service = OutputGuardrailService(
        pii_detector=pii_detector,
        harmful_content_judge=HarmfulContentJudge(judge=failing_judge),
    )

    result = await service.review(content="An answer that was never checked.")

    assert result.action is GuardrailActionEnum.BLOCKED
    assert result.harmful is not None and result.harmful.harmful is True
    pii_detector.review.assert_not_called()
