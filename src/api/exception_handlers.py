"""
Global exception handlers for the API.

This module defines centralized exception handlers that translate
domain and infrastructure errors into standardized, user-friendly
API responses.

The goal is to:
- Provide clear, non-technical messages to API consumers
- Prevent leaking internal implementation details
- Ensure consistent response structure across all failures
"""

from fastapi import FastAPI, Request

from src.core.constants import (
    ERROR_INTERVAL_SERVER_ERROR,
    ERROR_PERSISTENCE,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from src.core.exceptions import AppError, DomainError, PersistenceError
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.schemas.base import ErrorDetailModel

logger = get_logger(__name__)


def domain_exception_handler(_: Request, exc: DomainError) -> ApiResponse:
    """
    Handle domain-level (expected) application errors.

    Domain errors represent business-rule violations or
    client-visible failures (e.g. resource not found,
    invalid operation, or state conflicts).

    These errors:
    - Are safe to expose to API consumers
    - Typically map to HTTP 4xx status codes
    - Use clear, human-readable messages
    """
    # Log at warning level because this is an expected failure mode
    logger.exception(
        "Domain error occurred",
        extra={
            "error_code": exc.error_code,
            "detail": str(exc),
        },
    )

    return ApiResponse(
        success=False,
        status_code=exc.status_code,
        # DomainError messages are already user-friendly by design
        error=ErrorDetailModel(
            code=exc.error_code,
            message=str(exc),
        ),
    )


def persistence_exception_handler(_: Request, exc: PersistenceError) -> ApiResponse:
    """
    Handle infrastructure and persistence-layer failures.

    These errors indicate problems with underlying systems
    such as databases, caches, or external services.

    Notes:
    - Internal details are never exposed to clients
    - Always returns HTTP 500
    - Full exception details are logged for debugging
    """
    # Log full stack trace for internal diagnostics
    logger.exception("Persistence layer failure")

    return ApiResponse(
        success=False,
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        error=ErrorDetailModel(
            code=ERROR_PERSISTENCE,
            message=(
                "We're having trouble accessing our data right now. "
                "Please try again in a few moments."
            ),
        ),
    )


def handle_app_error(_: Request, exc: AppError) -> ApiResponse:
    """
    Register application exception handlers.
    """
    # Log at warning level because this is an expected failure mode
    logger.exception(
        "Application error occurred",
        extra={
            "error_code": exc.error_code,
            "detail": str(exc),
        },
    )

    return ApiResponse(
        message=exc.message,
        error=ErrorDetailModel(
            code=exc.error_code,
            message=str(exc),
        ),
        status_code=exc.status_code,
    )


def unhandled_exception_handler(_: Request, exc: Exception) -> ApiResponse:
    """
    Catch-all handler for unexpected and uncategorized exceptions.

    This handler acts as a final safety net to:
    - Prevent internal stack traces from leaking to clients
    - Guarantee a consistent error response format
    - Provide a calm, user-friendly error message
    """
    # Log full exception details for investigation
    logger.exception("Unhandled application error")

    return ApiResponse(
        success=False,
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        error=ErrorDetailModel(
            code=ERROR_INTERVAL_SERVER_ERROR,
            message=("Something went wrong on our side. " "Please try again later."),
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all global exception handlers with the FastAPI app.

    Centralizing exception handler registration keeps the application
    setup clean and ensures consistent error handling behavior
    across all endpoints.
    """
    app.add_exception_handler(DomainError, domain_exception_handler)
    app.add_exception_handler(PersistenceError, persistence_exception_handler)
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(Exception, unhandled_exception_handler)
