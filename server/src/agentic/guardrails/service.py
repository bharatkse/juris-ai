"""
Output guardrail service.

Single entry point AIOrchestrator calls (handle() and resume()) after
aggregation, before the final response is built -- see this package's
__init__.py for the architectural boundary against agentic.evaluation.
"""

from __future__ import annotations

import asyncio

from adapters.observability.logger import get_logger
from agentic.guardrails.harmful_content import HarmfulContentJudge
from agentic.guardrails.pii import PresidioPIIDetector
from agentic.guardrails.schemas import GuardrailActionEnum, GuardrailReviewResult, max_severity

logger = get_logger(__name__)


class OutputGuardrailService:
    """
    Reviews a final response for PII and harmful content before it is
    allowed to leave the system.

    Harmful content is checked first and short-circuits PII review:
    a BLOCKED response's content is meaningless (the caller must
    regenerate or fall back), so there is nothing useful for the PII
    detector to redact in it.
    """

    def __init__(
        self,
        *,
        pii_detector: PresidioPIIDetector,
        harmful_content_judge: HarmfulContentJudge,
    ) -> None:
        self._pii_detector = pii_detector
        self._harmful_content_judge = harmful_content_judge

    async def review(
        self,
        *,
        content: str,
        evidence_text: str = "",
    ) -> GuardrailReviewResult:
        """
        Review ``content`` (the final, aggregated response text)
        against ``evidence_text`` (retrieved evidence for this turn,
        used for the PII detector's provenance check -- see pii.py).
        """

        harmful = await self._harmful_content_judge.evaluate(content=content)

        if harmful.harmful:
            logger.warning(
                "Output guardrail blocked a response for harmful content.",
                extra={
                    "operation": "output_guardrail_review",
                    "category": harmful.category,
                },
            )

            return GuardrailReviewResult(
                content=content,
                action=GuardrailActionEnum.BLOCKED,
                harmful=harmful,
            )

        # PII review is synchronous/CPU-bound (spaCy inference) --
        # dispatched to a worker thread so it doesn't block the event
        # loop other concurrent requests are running on.
        redacted_content, detections = await asyncio.to_thread(
            self._pii_detector.review,
            text=content,
            evidence_text=evidence_text,
        )

        action = max_severity([detection.action for detection in detections])

        if action is not GuardrailActionEnum.NONE:
            logger.info(
                "Output guardrail reviewed a response.",
                extra={
                    "operation": "output_guardrail_review",
                    "action": action.value,
                    "detection_count": len(detections),
                    "categories": sorted({d.entity_type for d in detections}),
                },
            )

        return GuardrailReviewResult(
            content=redacted_content,
            action=action,
            detections=detections,
            harmful=harmful,
        )
