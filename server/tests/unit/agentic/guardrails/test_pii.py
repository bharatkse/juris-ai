"""
Unit tests for PresidioPIIDetector.

Uses the real Presidio AnalyzerEngine/AnonymizerEngine and the real
en_core_web_sm spaCy model (not mocked) -- the whole point of these
tests is verifying the actual detection/redaction behavior the
category-default-action design (see pii.py's module docstring)
produces, which a mocked analyzer couldn't demonstrate. The detector
is built once per module (spaCy model load is the expensive part) and
reused across tests.
"""

from __future__ import annotations

import pytest

from agentic.guardrails.pii import PresidioPIIDetector
from agentic.guardrails.schemas import GuardrailActionEnum, PIICategoryEnum


@pytest.fixture(scope="module")
def detector() -> PresidioPIIDetector:
    return PresidioPIIDetector()


def test_structured_id_is_always_redacted(detector: PresidioPIIDetector) -> None:
    """
    A structured identifier (PAN, the custom India-specific
    recognizer) is redacted regardless of whether it appears in
    retrieved evidence -- the STRUCTURED_ID category's default action
    never depends on provenance.
    """

    text = "The applicant's PAN is ABCDE1234F, filed under s.43A."

    redacted, detections = detector.review(
        text=text,
        evidence_text="The applicant's PAN is ABCDE1234F, filed under s.43A.",
    )

    assert "ABCDE1234F" not in redacted

    pan_detections = [d for d in detections if d.entity_type == "IN_PAN"]
    assert len(pan_detections) == 1
    assert pan_detections[0].category is PIICategoryEnum.STRUCTURED_ID
    assert pan_detections[0].action is GuardrailActionEnum.REDACTED


def test_named_entity_present_in_evidence_is_flagged_not_redacted(
    detector: PresidioPIIDetector,
) -> None:
    """
    A person's name that also appears in this turn's retrieved
    evidence is expected legal content (e.g. a citation naming a real
    case party) -- flagged for visibility, not redacted, so a correct
    answer doesn't get corrupted.
    """

    text = "Ramesh Kumar filed the case under the IT Act."
    evidence = "Case record: Ramesh Kumar vs State, filed 2024."

    redacted, detections = detector.review(text=text, evidence_text=evidence)

    assert "Ramesh Kumar" in redacted

    person_detections = [d for d in detections if d.entity_type == "PERSON"]
    assert person_detections
    assert all(d.action is GuardrailActionEnum.FLAGGED for d in person_detections)
    assert all(d.evidence_matched for d in person_detections)


def test_named_entity_absent_from_evidence_is_redacted(
    detector: PresidioPIIDetector,
) -> None:
    """
    A person's name with no basis in this turn's retrieved evidence
    is a stronger hallucination/leak signal than one drawn from real
    source content -- redacted by default, per the design in pii.py's
    docstring.
    """

    text = "The court noted that Sunita Verma was the complainant."
    evidence = "An unrelated retrieved chunk discussing e-signatures."

    redacted, detections = detector.review(text=text, evidence_text=evidence)

    assert "Sunita Verma" not in redacted

    person_detections = [d for d in detections if d.entity_type == "PERSON"]
    assert person_detections
    assert all(d.action is GuardrailActionEnum.REDACTED for d in person_detections)
    assert all(not d.evidence_matched for d in person_detections)


def test_contact_info_present_in_evidence_is_flagged(
    detector: PresidioPIIDetector,
) -> None:
    """
    Contact info (email/phone) is the CONTACT category -- same
    evidence-aware behavior as named entities, distinct from the
    always-redact STRUCTURED_ID category.
    """

    text = "You can reach the registrar at registrar@example.com."
    evidence = "Official notice: contact registrar@example.com for filings."

    redacted, detections = detector.review(text=text, evidence_text=evidence)

    assert "registrar@example.com" in redacted

    email_detections = [d for d in detections if d.entity_type == "EMAIL_ADDRESS"]
    assert email_detections
    assert all(d.action is GuardrailActionEnum.FLAGGED for d in email_detections)


def test_empty_text_produces_no_detections(detector: PresidioPIIDetector) -> None:
    redacted, detections = detector.review(text="", evidence_text="anything")

    assert redacted == ""
    assert detections == ()


def test_clean_text_produces_no_detections(detector: PresidioPIIDetector) -> None:
    text = "The statute defines electronic signature under section 2(1)(ta)."

    redacted, detections = detector.review(text=text, evidence_text="")

    assert redacted == text
    assert detections == ()


def test_overlapping_detections_are_resolved_without_raising(
    detector: PresidioPIIDetector,
) -> None:
    """
    A PAN-shaped string also fires the generic PERSON NER recognizer
    at the exact same span (both tie at score 0.85) -- overlap
    resolution (_resolve_overlaps) must deterministically keep the
    more specific IN_PAN detection (never PERSON, and never let it
    depend on recognizer iteration order -- confirmed non-deterministic
    before category-priority tie-breaking was added) and never pass
    both overlapping results to AnonymizerEngine.anonymize(), which
    raises on overlapping spans.
    """

    text = "His PAN is ABCDE1234F."

    for _ in range(5):
        redacted, detections = detector.review(text=text, evidence_text="")

        assert "ABCDE1234F" not in redacted
        assert "[REDACTED:IN_PAN]" in redacted
        assert not any(
            d.entity_type == "PERSON" for d in detections
        ), "PERSON must never win the tie against IN_PAN at the same span"
