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

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "Execution retry max_attempts must be greater than zero.",
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
