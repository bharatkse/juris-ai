"""
Unit tests for execution runtime configuration.
"""

from __future__ import annotations

import pytest

from agentic.execution.config import ExecutionRetryPolicy, ExecutionTimeoutPolicy


def test_execution_retry_policy_defaults() -> None:
    """
    It should use the default retry configuration.
    """

    policy = ExecutionRetryPolicy()

    assert policy.max_attempts == 3
    assert policy.max_retries == 2


def test_execution_retry_policy_calculates_max_retries() -> None:
    """
    It should calculate retries from the configured maximum attempts.
    """

    policy = ExecutionRetryPolicy(
        max_attempts=5,
    )

    assert policy.max_attempts == 5
    assert policy.max_retries == 4


def test_execution_retry_policy_rejects_invalid_attempts() -> None:
    """
    It should reject a retry policy with zero or negative attempts.
    """

    with pytest.raises(
        ValueError,
        match="Execution retry max_attempts must be greater than zero.",
    ):
        ExecutionRetryPolicy(
            max_attempts=0,
        )

    with pytest.raises(
        ValueError,
        match="Execution retry max_attempts must be greater than zero.",
    ):
        ExecutionRetryPolicy(
            max_attempts=-1,
        )


def test_execution_retry_policy_is_immutable() -> None:
    """
    It should not allow runtime mutation.
    """

    policy = ExecutionRetryPolicy()

    with pytest.raises(
        AttributeError,
    ):
        policy.max_attempts = 5


def test_execution_timeout_policy_defaults() -> None:
    """
    It should use the default execution timeout.
    """

    policy = ExecutionTimeoutPolicy()

    assert policy.timeout_seconds == 300.0


def test_execution_timeout_policy_accepts_custom_timeout() -> None:
    """
    It should accept a custom positive timeout.
    """

    policy = ExecutionTimeoutPolicy(
        timeout_seconds=30.0,
    )

    assert policy.timeout_seconds == 30.0


def test_execution_timeout_policy_rejects_zero_timeout() -> None:
    """
    It should reject a zero timeout.
    """

    with pytest.raises(
        ValueError,
        match="Execution timeout_seconds must be greater than zero.",
    ):
        ExecutionTimeoutPolicy(
            timeout_seconds=0,
        )


def test_execution_timeout_policy_rejects_negative_timeout() -> None:
    """
    It should reject a negative timeout.
    """

    with pytest.raises(
        ValueError,
        match="Execution timeout_seconds must be greater than zero.",
    ):
        ExecutionTimeoutPolicy(
            timeout_seconds=-1,
        )


def test_execution_timeout_policy_is_immutable() -> None:
    """
    It should not allow runtime mutation.
    """

    policy = ExecutionTimeoutPolicy()

    with pytest.raises(
        AttributeError,
    ):
        policy.timeout_seconds = 60.0
