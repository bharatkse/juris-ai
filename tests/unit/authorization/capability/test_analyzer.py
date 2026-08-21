from unittest.mock import Mock

from src.authorization.capability.analyzer import ExternalActionAnalyzer
from src.core.dto.capability import CapabilityMatchDTO
from src.core.enums import ActionTypeEnum


def test_analyze_returns_send_capability() -> None:
    classifier = Mock()

    classifier.classify.return_value = (
        CapabilityMatchDTO(
            action=ActionTypeEnum.SEND,
            score=0.91,
        ),
    )

    analyzer = ExternalActionAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Send this email to the client.",
    )

    assert result.actions == (ActionTypeEnum.SEND,)

    assert result.reason == ("Detected externally impactful actions: send.")

    classifier.classify.assert_called_once_with(
        "Send this email to the client.",
    )


def test_analyze_returns_empty_actions_when_no_external_action() -> None:
    classifier = Mock()
    classifier.classify.return_value = ()

    analyzer = ExternalActionAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Analyze this contract.",
    )

    assert result.actions == ()

    assert result.reason == ("No externally impactful action was identified.")


def test_analyze_supports_multiple_matches() -> None:
    classifier = Mock()

    classifier.classify.return_value = (
        CapabilityMatchDTO(
            action=ActionTypeEnum.SEND,
            score=0.91,
        ),
    )

    analyzer = ExternalActionAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Draft and send the email.",
    )

    assert result.actions == (ActionTypeEnum.SEND,)
