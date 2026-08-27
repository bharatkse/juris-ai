"""
Execution retry classification.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import final


@final
class RetryClassifier:
    """
    Determines whether an execution failure may be retried.

    Retryability is explicit. Unknown exceptions are considered
    non-retryable by default to prevent accidental retry amplification.
    """

    def __init__(
        self,
        *,
        retryable_exceptions: Sequence[type[BaseException]] = (),
    ) -> None:
        self._retryable_exceptions = tuple(
            retryable_exceptions,
        )

    def is_retryable(
        self,
        *,
        error: BaseException,
    ) -> bool:
        """
        Return whether the supplied exception is retryable.
        """

        return isinstance(
            error,
            self._retryable_exceptions,
        )
