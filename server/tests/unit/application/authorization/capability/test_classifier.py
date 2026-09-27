"""
Unit tests for TF-IDF capability classification.
"""

from __future__ import annotations

import pytest

from application.authorization.capability.classifier import TFIDFCapabilityClassifier
from core.enums import ActionTypeEnum


def test_init_rejects_empty_examples() -> None:
    """
    It should reject an empty capability example set.
    """

    with pytest.raises(
        ValueError,
        match="Capability examples cannot be empty",
    ):
        TFIDFCapabilityClassifier(
            examples={},
        )


@pytest.mark.parametrize(
    "threshold",
    (
        -0.01,
        1.01,
    ),
)
def test_init_rejects_invalid_threshold(
    threshold: float,
    examples: dict[ActionTypeEnum, tuple[str, ...]],
) -> None:
    """
    It should reject thresholds outside the range 0..1.
    """

    with pytest.raises(
        ValueError,
        match="Capability threshold must be between 0 and 1",
    ):
        TFIDFCapabilityClassifier(
            examples=examples,
            threshold=threshold,
        )


@pytest.mark.parametrize(
    "threshold",
    (
        0.0,
        1.0,
    ),
)
def test_init_accepts_boundary_threshold(
    threshold: float,
    examples: dict[ActionTypeEnum, tuple[str, ...]],
) -> None:
    """
    It should accept threshold values at 0 and 1.
    """

    classifier = TFIDFCapabilityClassifier(
        examples=examples,
        threshold=threshold,
    )

    assert classifier is not None


def test_init_rejects_examples_containing_only_empty_values() -> None:
    """
    It should reject capability sets that contain no usable examples.
    """

    examples = {
        ActionTypeEnum.SEND: (
            "",
            "   ",
        ),
        ActionTypeEnum.READ: (),
    }

    with pytest.raises(
        ValueError,
        match="Capability examples cannot contain empty action sets",
    ):
        TFIDFCapabilityClassifier(
            examples=examples,
        )


def test_init_ignores_empty_examples() -> None:
    """
    It should ignore empty examples when valid examples are present.
    """

    classifier = TFIDFCapabilityClassifier(
        examples={
            ActionTypeEnum.SEND: (
                "",
                "   ",
                "send an email",
            ),
        },
    )

    matches = classifier.classify(
        "send an email",
    )

    assert len(matches) == 1
    assert matches[0].action_type == ActionTypeEnum.SEND


def test_classify_returns_matching_capability(
    classifier: TFIDFCapabilityClassifier,
) -> None:
    """
    It should identify the requested capability.
    """

    matches = classifier.classify(
        "Please send an email to the customer.",
    )

    assert len(matches) == 1
    assert matches[0].action_type == ActionTypeEnum.SEND
    assert matches[0].score >= 0.35


def test_classify_returns_multiple_capabilities(
    classifier: TFIDFCapabilityClassifier,
) -> None:
    """
    It should return multiple capabilities when the input
    matches multiple supported action types.
    """

    matches = classifier.classify(
        "Send the document and then read the document.",
    )

    action_types = {match.action_type for match in matches}

    assert ActionTypeEnum.SEND in action_types
    assert ActionTypeEnum.READ in action_types


def test_classify_returns_empty_tuple_for_empty_content(
    classifier: TFIDFCapabilityClassifier,
) -> None:
    """
    It should return no matches for empty content.
    """

    assert classifier.classify("") == ()
    assert classifier.classify("   ") == ()


def test_classify_excludes_matches_below_threshold(
    examples: dict[ActionTypeEnum, tuple[str, ...]],
) -> None:
    """
    It should exclude capabilities whose similarity score
    is below the configured threshold.
    """

    classifier = TFIDFCapabilityClassifier(
        examples=examples,
        threshold=0.99,
    )

    matches = classifier.classify(
        "completely unrelated content",
    )

    assert matches == ()


def test_classify_respects_similarity_threshold(
    classifier: TFIDFCapabilityClassifier,
) -> None:
    """
    It should only return capabilities whose similarity
    meets the configured threshold.
    """

    matches = classifier.classify(
        "The weather is beautiful today.",
    )

    assert all(match.score >= classifier._threshold for match in matches)


def test_classify_returns_at_most_one_match_per_action_type(
    examples: dict[ActionTypeEnum, tuple[str, ...]],
) -> None:
    """
    It should return only the highest-scoring match for each action type.
    """

    classifier = TFIDFCapabilityClassifier(
        examples=examples,
        threshold=0.0,
    )

    matches = classifier.classify(
        "send an email",
    )

    send_matches = [match for match in matches if match.action_type == ActionTypeEnum.SEND]

    assert len(send_matches) == 1


def test_classify_uses_highest_similarity_for_action_type() -> None:
    """
    It should retain the highest similarity score for an action type.
    """

    classifier = TFIDFCapabilityClassifier(
        examples={
            ActionTypeEnum.SEND: (
                "send an email",
                "send",
                "send a message to someone",
            ),
        },
        threshold=0.0,
    )

    matches = classifier.classify(
        "send an email",
    )

    assert len(matches) == 1
    assert matches[0].action_type == ActionTypeEnum.SEND
    assert matches[0].score > 0.0


def test_classify_is_case_insensitive(
    classifier: TFIDFCapabilityClassifier,
) -> None:
    """
    It should classify input regardless of letter casing.
    """

    lowercase = classifier.classify(
        "send an email",
    )

    uppercase = classifier.classify(
        "SEND AN EMAIL",
    )

    assert len(lowercase) == len(uppercase)
    assert lowercase[0].action_type == uppercase[0].action_type
    assert lowercase[0].score == pytest.approx(
        uppercase[0].score,
    )


def test_classify_strips_input_whitespace(
    classifier: TFIDFCapabilityClassifier,
) -> None:
    """
    It should ignore leading and trailing whitespace.
    """

    normal = classifier.classify(
        "send an email",
    )

    padded = classifier.classify(
        "   send an email   ",
    )

    assert len(normal) == len(padded)
    assert normal[0].action_type == padded[0].action_type
    assert normal[0].score == pytest.approx(
        padded[0].score,
    )


def test_classify_returns_capability_match_dto(
    classifier: TFIDFCapabilityClassifier,
) -> None:
    """
    It should return CapabilityMatchDTO instances.
    """

    matches = classifier.classify(
        "send an email",
    )

    assert len(matches) == 1

    match = matches[0]

    assert match.action_type == ActionTypeEnum.SEND
    assert isinstance(match.score, float)
