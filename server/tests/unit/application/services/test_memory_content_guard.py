"""
Unit tests for MemoryContentGuard.

Two layers are tested separately on purpose. The regex hard-blocks must
hold with NO help from Presidio (they run even if it is missing, broken
or simply misses a format); the Presidio layer is tested both with a fake
detector (policy) and against the real one (behaviour, including its
measured weaknesses).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agentic.guardrails.schemas import GuardrailActionEnum, PIICategoryEnum, PIIDetection
from application.services.memory_content_guard import MemoryContentGuard


def _detection(entity: str, category: PIICategoryEnum) -> PIIDetection:
    return PIIDetection(
        entity_type=entity,
        category=category,
        action=GuardrailActionEnum.REDACTED,
        evidence_matched=False,
    )


def _guard(*detections: PIIDetection) -> tuple[MemoryContentGuard, MagicMock]:
    detector = MagicMock()
    detector.review.return_value = ("", tuple(detections))

    return MemoryContentGuard(pii_detector=detector), detector


# ----------------------------------------------------------------------
# Layer 1: hard-block patterns, independent of Presidio
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Aadhaar is 2345 6789 0123", "aadhaar"),
        ("Aadhaar is 234567890123", "aadhaar"),
        ("Aadhaar is 2345-6789-0123", "aadhaar"),
        ("PAN is ABCDE1234F", "pan"),
        ("pan is abcde1234f", "pan"),
        ("IFSC code HDFC0001234", "ifsc"),
        ("Account number 123456789012345", "account_or_card_number"),
        ("Account 1234 5678 9012 3456", "account_or_card_number"),
        ("Card 4111-1111-1111-1111", "account_or_card_number"),
        ("UPI id is rahul@okhdfcbank", "payment_or_email_handle"),
        ("Email rahul@example.com", "payment_or_email_handle"),
    ],
)
def test_identifier_patterns_are_hard_blocked_with_no_help_from_presidio(
    text: str,
    reason: str,
) -> None:
    assert reason in MemoryContentGuard.hard_block_reasons(text)


@pytest.mark.parametrize(
    "text",
    [
        "Prefers concise answers with bullet points",
        "Practises before the Delhi High Court",
        "Drafts contracts under the Indian Contract Act 1872",
        "Has 15 years of experience in arbitration",
        "Prefers responses in Hindi",
        "Likes citations in OSCOLA style",
        # Short digit runs and a code-like token are not identifiers.
        "Uses section 138 of the Negotiable Instruments Act",
        "Prefers a 2 page summary",
    ],
)
def test_ordinary_preferences_are_not_hard_blocked(text: str) -> None:
    assert MemoryContentGuard.hard_block_reasons(text) == ()


async def test_a_hard_block_rejects_without_ever_calling_presidio() -> None:
    guard, detector = _guard()

    verdict = await guard.check("Their PAN is ABCDE1234F")

    assert verdict.allowed is False
    assert "pan" in verdict.reasons
    detector.review.assert_not_called()


async def test_hard_blocks_hold_even_when_presidio_finds_nothing() -> None:
    guard, _ = _guard()  # a detector that "sees" no PII at all

    verdict = await guard.check("Aadhaar 2345 6789 0123")

    assert verdict.allowed is False


async def test_hard_blocks_hold_even_when_presidio_is_broken() -> None:
    detector = MagicMock()
    detector.review.side_effect = RuntimeError("spaCy model failed to load")
    guard = MemoryContentGuard(pii_detector=detector)

    verdict = await guard.check("Bank account 123456789012")

    assert verdict.allowed is False
    assert "account_or_card_number" in verdict.reasons


# ----------------------------------------------------------------------
# Layer 2: Presidio policy
# ----------------------------------------------------------------------


async def test_clean_content_is_allowed() -> None:
    guard, detector = _guard()

    verdict = await guard.check("Prefers concise answers")

    assert verdict.allowed is True
    assert verdict.reasons == ()
    detector.review.assert_called_once()


@pytest.mark.parametrize(
    ("entity", "category", "reason"),
    [
        ("IN_PAN", PIICategoryEnum.STRUCTURED_ID, "structured_id:IN_PAN"),
        ("CREDIT_CARD", PIICategoryEnum.STRUCTURED_ID, "structured_id:CREDIT_CARD"),
        ("EMAIL_ADDRESS", PIICategoryEnum.CONTACT, "contact:EMAIL_ADDRESS"),
        ("PHONE_NUMBER", PIICategoryEnum.CONTACT, "contact:PHONE_NUMBER"),
        ("PERSON", PIICategoryEnum.NAMED_ENTITY, "named_entity:PERSON"),
        ("ORGANIZATION", PIICategoryEnum.NAMED_ENTITY, "named_entity:ORGANIZATION"),
    ],
)
async def test_presidio_structured_ids_contacts_people_and_organizations_are_rejected(
    entity: str,
    category: PIICategoryEnum,
    reason: str,
) -> None:
    guard, _ = _guard(_detection(entity, category))

    verdict = await guard.check("Some perfectly ordinary looking sentence")

    assert verdict.allowed is False
    assert verdict.reasons == (reason,)


async def test_locations_are_allowed() -> None:
    # A court's city, a jurisdiction, a language: useful and not a client.
    guard, _ = _guard(_detection("LOCATION", PIICategoryEnum.NAMED_ENTITY))

    assert (await guard.check("Practises in Mumbai")).allowed is True


async def test_every_reason_is_reported_once() -> None:
    guard, _ = _guard(
        _detection("PERSON", PIICategoryEnum.NAMED_ENTITY),
        _detection("PERSON", PIICategoryEnum.NAMED_ENTITY),
        _detection("EMAIL_ADDRESS", PIICategoryEnum.CONTACT),
    )

    verdict = await guard.check("Some sentence")

    assert verdict.reasons == ("named_entity:PERSON", "contact:EMAIL_ADDRESS")


async def test_it_fails_closed_when_the_presidio_check_itself_errors() -> None:
    detector = MagicMock()
    detector.review.side_effect = RuntimeError("boom")
    guard = MemoryContentGuard(pii_detector=detector)

    verdict = await guard.check("Prefers concise answers")

    assert verdict.allowed is False
    assert verdict.reasons == ("pii_check_unavailable",)


async def test_verdicts_never_contain_the_matched_text() -> None:
    guard, _ = _guard(_detection("PERSON", PIICategoryEnum.NAMED_ENTITY))
    secret = "ABCDE1234F"

    for text in (f"PAN {secret}", "Advocate Sharma prefers brevity"):
        verdict = await guard.check(text)

        assert secret not in repr(verdict)
        assert "Sharma" not in repr(verdict)


# ----------------------------------------------------------------------
# The real Presidio detector (loads spaCy once, a few seconds)
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_guard() -> MemoryContentGuard:
    from agentic.guardrails.pii import PresidioPIIDetector

    return MemoryContentGuard(pii_detector=PresidioPIIDetector())


@pytest.mark.slow
@pytest.mark.parametrize(
    "text",
    [
        "Their PAN is ABCDE1234F",
        "Aadhaar 2345 6789 0123",
        "Contact them at rahul@example.com",
        "Client is Acme Holdings Pvt Ltd in a merger dispute",
    ],
)
async def test_real_presidio_rejects_identifiers_contacts_and_company_names(
    real_guard: MemoryContentGuard,
    text: str,
) -> None:
    assert (await real_guard.check(text)).allowed is False


@pytest.mark.slow
@pytest.mark.parametrize(
    "text",
    [
        "Prefers concise answers with bullet points",
        "Practises before the Delhi High Court",
        "Practises in Mumbai and mainly handles arbitration",
        "Prefers responses in Hindi",
    ],
)
async def test_real_presidio_allows_ordinary_preferences_and_locations(
    real_guard: MemoryContentGuard,
    text: str,
) -> None:
    assert (await real_guard.check(text)).allowed is True


@pytest.mark.slow
@pytest.mark.xfail(
    strict=False,
    reason=(
        "KNOWN LIMIT, measured: en_core_web_sm does not detect 'Advocate Sharma' as a "
        "PERSON, so a person's name can slip past the NER layer. The extraction prompt "
        "forbids names and users can view/delete every memory; this layer is best-effort. "
        "Tracked for the Phase 2 extraction-precision eval."
    ),
)
async def test_real_presidio_should_reject_a_bare_person_name(
    real_guard: MemoryContentGuard,
) -> None:
    assert (await real_guard.check("Prefers to be addressed as Advocate Sharma")).allowed is False


@pytest.mark.slow
@pytest.mark.xfail(
    strict=False,
    reason=(
        "KNOWN OVER-BLOCK, measured: statute names such as 'Indian Contract Act 1872' are "
        "tagged ORGANIZATION, so facts naming a statute are rejected. The privacy-first "
        "default; tracked for the Phase 2 extraction-precision eval."
    ),
)
async def test_real_presidio_should_allow_a_fact_naming_a_statute(
    real_guard: MemoryContentGuard,
) -> None:
    assert (
        await real_guard.check("Drafts contracts under the Indian Contract Act 1872")
    ).allowed is True


def test_the_guard_only_needs_the_review_method() -> None:
    # Guard against widening the coupling to Presidio's concrete class.
    fake = SimpleNamespace(review=lambda *, text, evidence_text: (text, ()))

    assert MemoryContentGuard(pii_detector=fake) is not None  # type: ignore[arg-type]
