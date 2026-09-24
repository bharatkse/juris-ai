"""
Content guard for facts about to be saved to long-term memory.

Two independent layers, both must pass:

1. Hard-block patterns -- Aadhaar, PAN, IFSC, bank-account/card-length
   digit runs, and payment/contact handles. Plain regexes that run first
   and do not depend on Presidio, so they hold even if it fails,
   is misconfigured, or simply misses a format. These reject; they never
   redact, because a memory with a hole in it is not a usable fact.

2. Presidio (the same detector the output guardrail uses) -- structured
   ids and contact details are always rejected. Person and organization
   names are rejected too, since in a legal product they are most likely
   a client or a counterparty, and long-term memory is exactly where a
   name from one matter must not be carried into another. Locations are
   allowed (a court's city, a jurisdiction, a language).

Known limits, measured on real sentences rather than assumed:

* Person-name detection is best-effort. The small spaCy model misses
  real names ("Advocate Sharma" produced no detection), so this layer is
  NOT a guarantee that a client's name cannot be stored. The extraction
  prompt (which forbids names) and the user's ability to view and delete
  every memory are the other controls.
* Organization detection over-blocks: statutes ("Indian Contract Act
  1872") are tagged as organizations, so a fact that names one is
  rejected. That is the cost of the privacy-first default and is tracked
  for the Phase 2 extraction-precision eval.

If the Presidio check itself raises, the guard fails closed: the
content is rejected. Verdicts carry category labels only -- never the
matched text, which is user data.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from adapters.observability.logger import get_logger
from agentic.guardrails.schemas import PIICategoryEnum

if TYPE_CHECKING:
    from agentic.guardrails.schemas import PIIDetection

logger = get_logger(__name__)

# Digit groups separated by spaces or hyphens ("2345 6789 0123",
# "1234-5678-9012-3456") are compacted before the digit-run checks, so
# formatting cannot be used to slip an identifier past them.
_DIGIT_SEPARATORS = re.compile(r"(?<=\d)[\s\-]+(?=\d)")

# name, pattern, whether it runs on the digit-compacted text.
_HARD_BLOCKS: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    # Aadhaar: 12 digits, first digit 2-9.
    ("aadhaar", re.compile(r"(?<!\d)[2-9]\d{11}(?!\d)"), True),
    # Bank account numbers and card numbers: 9-19 digits in a row. Also
    # catches long phone numbers and reference numbers -- an accepted
    # over-block for a safety guard.
    ("account_or_card_number", re.compile(r"(?<!\d)\d{9,19}(?!\d)"), True),
    # PAN: 5 letters, 4 digits, 1 letter. Case-insensitive because the
    # model may normalize case.
    ("pan", re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b"), False),
    # IFSC: 4 letters, a literal zero, 6 alphanumerics.
    ("ifsc", re.compile(r"\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b"), False),
    # UPI ids and email addresses: anything shaped like handle@provider.
    ("payment_or_email_handle", re.compile(r"[\w.\-]{2,}@[A-Za-z][\w\-]+"), False),
)

# Named-entity types that are rejected. LOCATION is deliberately absent.
_BLOCKED_NAMED_ENTITIES = frozenset({"PERSON", "ORGANIZATION"})


class PIIDetectorProtocol(Protocol):
    """
    The slice of PresidioPIIDetector this guard uses.
    """

    def review(
        self,
        *,
        text: str,
        evidence_text: str,
    ) -> tuple[str, tuple[PIIDetection, ...]]: ...


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    """
    Whether content may be stored, and why not. ``reasons`` are category
    labels (e.g. "aadhaar", "named_entity:PERSON"), never matched text.
    """

    allowed: bool

    reasons: tuple[str, ...] = ()


class MemoryContentGuard:
    """
    Decide whether a candidate memory may be persisted.
    """

    def __init__(
        self,
        *,
        pii_detector: PIIDetectorProtocol,
    ) -> None:
        self._pii_detector = pii_detector

    @staticmethod
    def hard_block_reasons(
        content: str,
    ) -> tuple[str, ...]:
        """
        Reasons from the regex layer alone. Synchronous, no I/O, and
        independent of Presidio.
        """

        compacted = _DIGIT_SEPARATORS.sub("", content)

        return tuple(
            name
            for name, pattern, on_compacted in _HARD_BLOCKS
            if pattern.search(compacted if on_compacted else content)
        )

    async def check(
        self,
        content: str,
    ) -> GuardVerdict:
        """
        Run both layers. The regex layer runs first, and Presidio is
        skipped entirely when it already rejects.
        """

        reasons = list(self.hard_block_reasons(content))

        if reasons:
            return GuardVerdict(allowed=False, reasons=tuple(reasons))

        try:
            # Presidio is synchronous and CPU-bound (spaCy inference):
            # never run it on the event loop.
            _, detections = await asyncio.to_thread(
                self._pii_detector.review,
                text=content,
                evidence_text="",
            )

        except Exception:
            logger.exception(
                "PII check failed while screening a memory; rejecting it.",
                extra={"operation": "memory_content_guard"},
            )

            return GuardVerdict(allowed=False, reasons=("pii_check_unavailable",))

        for detection in detections:
            reason = self._reason_for(detection)

            if reason is not None and reason not in reasons:
                reasons.append(reason)

        return GuardVerdict(allowed=not reasons, reasons=tuple(reasons))

    @staticmethod
    def _reason_for(
        detection: PIIDetection,
    ) -> str | None:
        if detection.category in (
            PIICategoryEnum.STRUCTURED_ID,
            PIICategoryEnum.CONTACT,
        ):
            return f"{detection.category.value}:{detection.entity_type}"

        if (
            detection.category is PIICategoryEnum.NAMED_ENTITY
            and detection.entity_type in _BLOCKED_NAMED_ENTITIES
        ):
            return f"named_entity:{detection.entity_type}"

        return None
