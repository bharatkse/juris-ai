"""
Unit tests for capability analysis.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from application.authorization.capability.analyzer import DefaultCapabilityAnalyzer
from core.dto.capability import CapabilityMatchDTO
from core.enums import ActionTypeEnum


def build_match(
    action_type: ActionTypeEnum,
    score: float = 0.90,
) -> CapabilityMatchDTO:
    """
    Build a capability match DTO.
    """

    return CapabilityMatchDTO(
        action_type=action_type,
        score=score,
    )


def test_analyze_returns_detected_capabilities() -> None:
    """
    It should return the action types detected by the classifier.
    """

    classifier = MagicMock()

    classifier.classify.return_value = (
        build_match(
            ActionTypeEnum.SEND,
        ),
    )

    analyzer = DefaultCapabilityAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Send the document.",
    )

    assert result.action_types == (ActionTypeEnum.SEND,)

    assert result.has_capabilities is True

    assert result.reason == ("Detected requested capabilities: send.")

    classifier.classify.assert_called_once_with(
        "Send the document.",
    )


def test_analyze_returns_multiple_detected_capabilities() -> None:
    """
    It should return multiple detected action types.
    """

    classifier = MagicMock()

    classifier.classify.return_value = (
        build_match(
            ActionTypeEnum.SEND,
            score=0.95,
        ),
        build_match(
            ActionTypeEnum.AGENT_CALL,
            score=0.88,
        ),
    )

    analyzer = DefaultCapabilityAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Send this to another agent.",
    )

    assert result.action_types == (
        ActionTypeEnum.SEND,
        ActionTypeEnum.AGENT_CALL,
    )

    assert result.has_capabilities is True

    assert result.reason == ("Detected requested capabilities: send, agent_call.")


def test_analyze_returns_empty_actions_when_no_capability_is_detected() -> None:
    """
    It should return no action types when nothing is detected.
    """

    classifier = MagicMock()

    classifier.classify.return_value = ()

    analyzer = DefaultCapabilityAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Hello, how are you?",
    )

    assert result.action_types == ()
    assert result.has_capabilities is False

    assert result.reason == ("No supported capability was identified.")


def test_analyze_preserves_classifier_action_order() -> None:
    """
    It should preserve the order returned by the classifier.
    """

    classifier = MagicMock()

    classifier.classify.return_value = (
        build_match(
            ActionTypeEnum.AGENT_CALL,
        ),
        build_match(
            ActionTypeEnum.SEND,
        ),
    )

    analyzer = DefaultCapabilityAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Send this to another agent.",
    )

    assert result.action_types == (
        ActionTypeEnum.AGENT_CALL,
        ActionTypeEnum.SEND,
    )


def test_analyze_ignores_match_scores_in_analysis_result() -> None:
    """
    It should expose action types but not classifier scores
    in the analysis result.
    """

    classifier = MagicMock()

    classifier.classify.return_value = (
        build_match(
            ActionTypeEnum.SEND,
            score=0.42,
        ),
    )

    analyzer = DefaultCapabilityAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Send the document.",
    )

    assert result.action_types == (ActionTypeEnum.SEND,)

    assert not hasattr(
        result,
        "score",
    )


def test_analyzer_uses_injected_classifier() -> None:
    """
    It should use the classifier supplied during construction.
    """

    classifier = MagicMock()

    classifier.classify.return_value = (
        build_match(
            ActionTypeEnum.SEND,
        ),
    )

    analyzer = DefaultCapabilityAnalyzer(
        classifier=classifier,
    )

    content = "Send the document."

    analyzer.analyze(
        content,
    )

    classifier.classify.assert_called_once_with(
        content,
    )


def test_analyze_is_synchronous() -> None:
    """
    It should expose a synchronous analysis API.
    """

    classifier = MagicMock()

    classifier.classify.return_value = ()

    analyzer = DefaultCapabilityAnalyzer(
        classifier=classifier,
    )

    result = analyzer.analyze(
        "Hello",
    )

    assert result.action_types == ()
    assert result.has_capabilities is False


def test_build_reason_for_no_capabilities() -> None:
    """
    It should return the expected reason when no capability is detected.
    """

    reason = DefaultCapabilityAnalyzer._build_reason(
        (),
    )

    assert reason == ("No supported capability was identified.")


@pytest.mark.parametrize(
    "action_type",
    list(ActionTypeEnum),
)
def test_build_reason_contains_detected_action(
    action_type: ActionTypeEnum,
) -> None:
    """
    It should include detected action types in the reason.
    """

    reason = DefaultCapabilityAnalyzer._build_reason(
        (action_type,),
    )

    assert reason == ("Detected requested capabilities: " f"{action_type.value}.")
