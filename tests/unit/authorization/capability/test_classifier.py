from src.authorization.capability.classifier import TFIDFCapabilityClassifier
from src.authorization.capability.examples import EXTERNAL_ACTION_EXAMPLES
from src.core.enums import ActionTypeEnum


def create_classifier() -> TFIDFCapabilityClassifier:
    return TFIDFCapabilityClassifier(
        examples=EXTERNAL_ACTION_EXAMPLES,
        threshold=0.35,
    )


def test_classifies_send_email() -> None:
    classifier = create_classifier()

    matches = classifier.classify(
        "Send this email to the client.",
    )

    assert matches
    assert matches[0].action == ActionTypeEnum.SEND


def test_classifies_send_document() -> None:
    classifier = create_classifier()

    matches = classifier.classify(
        "Please send the contract to the client.",
    )

    assert matches
    assert matches[0].action == ActionTypeEnum.SEND


def test_classifies_forward_document_as_send() -> None:
    classifier = create_classifier()

    matches = classifier.classify(
        "Forward this document to the client.",
    )

    assert matches
    assert matches[0].action == ActionTypeEnum.SEND


def test_does_not_classify_normal_request_as_send() -> None:
    classifier = create_classifier()

    matches = classifier.classify(
        "Analyze this contract.",
    )

    assert matches == ()


def test_does_not_classify_draft_email_as_send() -> None:
    classifier = create_classifier()

    matches = classifier.classify(
        "Draft an email to the client.",
    )

    assert matches == ()


def test_empty_content_returns_no_matches() -> None:
    classifier = create_classifier()

    matches = classifier.classify("")

    assert matches == ()
