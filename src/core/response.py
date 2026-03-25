"""
Standardized API response helpers for FastAPI.

This module provides a consistent JSON response envelope
for all API endpoints, ensuring uniform success and error
responses across the application.
"""

from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.core.constants import (
    HTTP_200_OK,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

# Generic type for response data payload
T = TypeVar("T")


class ResponsePayload(BaseModel, Generic[T]):
    """
    Standard API response payload schema.

    This model represents the serialized JSON body returned
    by all API responses.

    Attributes:
        success: Indicates whether the request was successful
        message: Human-readable message for clients
        data: Optional response payload
        error_code: Optional machine-readable error identifier
    """

    success: bool
    message: str | None = None
    data: T | None = None
    error_code: str | None = None


class ApiResponse(JSONResponse):
    """
    Standardized API response wrapper for FastAPI.

    This class enforces a consistent response structure
    across all endpoints by wrapping responses in a
    predictable JSON envelope.

    It also applies default headers and status code handling.
    """

    # Default response headers
    DEFAULT_HEADERS: dict[str, str] = {
        "Content-Type": "application/json",
    }

    # Default CORS headers (used if middleware is not applied)
    DEFAULT_CORS_HEADERS: dict[str, str] = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Expose-Headers": "X-Request-ID",
    }

    # Default HTTP status codes
    DEFAULT_SUCCESS_STATUS = HTTP_200_OK
    DEFAULT_ERROR_STATUS = HTTP_500_INTERNAL_SERVER_ERROR

    @classmethod
    def _build_headers(
        cls,
        *,
        extra_headers: Mapping[str, str] | None = None,
        cors_origin: str | None = None,
    ) -> dict[str, str]:
        """
        Build response headers by merging defaults with overrides.

        Args:
            extra_headers: Optional custom headers to include
            cors_origin: Optional specific CORS origin override

        Returns:
            Final merged headers dictionary
        """
        headers = {
            **cls.DEFAULT_HEADERS,
            **cls.DEFAULT_CORS_HEADERS,
        }

        # Override CORS origin if explicitly provided
        if cors_origin:
            headers["Access-Control-Allow-Origin"] = cors_origin

        # Merge any additional custom headers
        if extra_headers:
            headers |= dict(extra_headers)

        return headers

    def __init__(
        self,
        *,
        success: bool,
        message: str | None = None,
        data: Any | None = None,
        error_code: str | None = None,
        status_code: int | None = None,
        headers: Mapping[str, str] | None = None,
    ):
        """
        Initialize a standardized API response.

        Status code resolution logic:
        - If status_code is explicitly provided, use it
        - Otherwise:
            - 200 OK for success responses
            - 500 Internal Server Error for error responses

        Args:
            success: Indicates success or failure
            message: User-friendly response message
            data: Optional response payload
            error_code: Optional internal error identifier
            status_code: Optional HTTP status override
            headers: Optional custom response headers
        """
        # Construct response payload model
        payload: ResponsePayload[Any] = ResponsePayload(
            success=success,
            message=message,
            data=data,
            error_code=error_code,
        )

        # Determine HTTP status code
        if status_code is None:
            status_code = self.DEFAULT_SUCCESS_STATUS if success else self.DEFAULT_ERROR_STATUS

        # Initialize FastAPI JSONResponse
        super().__init__(
            content=jsonable_encoder(payload, exclude_none=True),
            status_code=status_code,
            headers=self._build_headers(extra_headers=headers),
        )

    @classmethod
    def success_response(
        cls,
        *,
        message: str | None = None,
        data: Any | None = None,
        status_code: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> "ApiResponse":
        """
        Create a standardized success response.

        Args:
            message: Success message for the client
            data: Optional response payload
            status_code: Optional HTTP status override
            headers: Optional custom headers

        Returns:
            ApiResponse instance representing a success response
        """
        return cls(
            success=True,
            message=message,
            data=data,
            status_code=status_code,
            headers=headers,
        )

    @classmethod
    def error_response(
        cls,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> "ApiResponse":
        """
        Create a standardized error response.

        Args:
            message: User-friendly error message
            error_code: Optional internal error identifier
            status_code: Optional HTTP status override
            headers: Optional custom headers

        Returns:
            ApiResponse instance representing an error response
        """
        return cls(
            success=False,
            message=message,
            error_code=error_code,
            status_code=status_code,
            headers=headers,
        )
