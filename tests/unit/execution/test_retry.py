"""
Unit tests for execution retry classification.
"""

from __future__ import annotations

from src.execution.retry import RetryClassifier


class RetryableError(Exception):
    """Test retryable exception."""


class NonRetryableError(Exception):
    """Test non-retryable exception."""


def test_retry_classifier_returns_false_by_default() -> None:
    """
    It should treat exceptions as non-retryable by default.
    """

    classifier = RetryClassifier()

    assert (
        classifier.is_retryable(
            error=RuntimeError("failure"),
        )
        is False
    )


def test_retry_classifier_returns_true_for_configured_exception() -> None:
    """
    It should classify configured exceptions as retryable.
    """

    classifier = RetryClassifier(
        retryable_exceptions=(RetryableError,),
    )

    assert (
        classifier.is_retryable(
            error=RetryableError("temporary failure"),
        )
        is True
    )


def test_retry_classifier_returns_false_for_unconfigured_exception() -> None:
    """
    It should classify unconfigured exceptions as non-retryable.
    """

    classifier = RetryClassifier(
        retryable_exceptions=(RetryableError,),
    )

    assert (
        classifier.is_retryable(
            error=NonRetryableError("permanent failure"),
        )
        is False
    )


def test_retry_classifier_supports_exception_inheritance() -> None:
    """
    It should treat subclasses of configured exceptions as retryable.
    """

    class ChildRetryableError(RetryableError):
        """Test retryable subclass."""

    classifier = RetryClassifier(
        retryable_exceptions=(RetryableError,),
    )

    assert (
        classifier.is_retryable(
            error=ChildRetryableError("temporary failure"),
        )
        is True
    )
