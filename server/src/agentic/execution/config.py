"""
Execution runtime configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ExecutionRetryPolicy:
    """
    Runtime retry policy.

    Retry configuration is execution-runtime configuration and is
    intentionally separate from ExecutionStepDTO.
    """

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "Execution retry max_attempts must be greater than zero.",
            )

        if self.base_delay_seconds < 0:
            raise ValueError(
                "Execution retry base_delay_seconds must not be negative.",
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "Execution retry max_delay_seconds must not be negative.",
            )

        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "Execution retry max_delay_seconds must be greater than "
                "or equal to base_delay_seconds.",
            )

    def delay_seconds(self, *, retry_count: int) -> float:
        """
        Return the capped exponential backoff for a scheduled retry.

        ``retry_count`` is one-based for the retry being scheduled:
        retry 1 waits ``base_delay_seconds``, retry 2 waits twice that,
        and so on, capped at ``max_delay_seconds``.
        """

        if retry_count < 1:
            raise ValueError(
                "Execution retry_count must be greater than zero.",
            )

        return min(
            self.base_delay_seconds * (2.0 ** (retry_count - 1)),
            self.max_delay_seconds,
        )

    @property
    def max_retries(self) -> int:
        """
        Return the number of retries allowed after the initial attempt.
        """

        return self.max_attempts - 1


@dataclass(slots=True, frozen=True)
class ExecutionTimeoutPolicy:
    """
    Runtime execution timeout policy.

    The timeout applies to the complete LangGraph execution for a
    single execution request.
    """

    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError(
                "Execution timeout_seconds must be greater than zero.",
            )
