"""
Aggregation exceptions.
"""

from __future__ import annotations

from src.core.constants import ERROR_AGGREGATION_FAILED, HTTP_500_INTERNAL_SERVER_ERROR
from src.core.exceptions.base import AppError


class AggregationError(AppError):
    """
    Base exception for aggregation failures.
    """

    def __init__(
        self,
        message: str = "Failed to aggregate agent responses.",
    ) -> None:
        super().__init__(
            message=message,
            error_code=ERROR_AGGREGATION_FAILED,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


class EmptyAggregationError(AggregationError):
    """
    Raised when no responses are available for aggregation.
    """

    def __init__(self) -> None:
        super().__init__(
            message="No agent responses available for aggregation.",
        )


class InvalidAggregationInputError(AggregationError):
    """
    Raised when aggregation input is invalid.
    """

    def __init__(
        self,
        message: str = "Invalid aggregation input.",
    ) -> None:
        super().__init__(
            message=message,
        )
