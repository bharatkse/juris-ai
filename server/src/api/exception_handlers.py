"""
Global exception handlers.

What a client sees of an error is built in one place, public_error(),
shared with the /chat/stream `error` event: the error code, the request ID
(also sent as X-Request-ID) and, for a client error (4xx), its message and
details. A server error (5xx) gets a generic message and no details, since
its text may describe internals, unless the error class is written for the
client (AppError.expose_message, e.g. the planning 503/504). The full error
is logged server-side.
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from adapters.observability.logger import get_logger
from api.utilities.api_response import ApiResponse
from core.constants import ERROR_INTERNAL_SERVER_ERROR, HTTP_500_INTERNAL_SERVER_ERROR
from core.exceptions.base import AppError
from core.models.response import ErrorDetailModel, MetadataModel

logger = get_logger(__name__)

GENERIC_ERROR_MESSAGE = "An unexpected error occurred. Please try again later."


def public_error(exc: BaseException, *, request_id: str | None) -> ErrorDetailModel:
    """
    The part of an error a client may see.
    """

    if isinstance(exc, AppError) and (exc.status_code < 500 or exc.expose_message):
        return ErrorDetailModel(
            code=exc.error_code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        )

    return ErrorDetailModel(
        code=exc.error_code if isinstance(exc, AppError) else ERROR_INTERNAL_SERVER_ERROR,
        message=GENERIC_ERROR_MESSAGE,
        request_id=request_id,
    )


def _request_id(request: Request) -> str | None:
    context = getattr(request.state, "context", None)
    return str(getattr(context, "request_id", None) or "") or None


def _error_response(
    *,
    error: ErrorDetailModel,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> ApiResponse:
    # The request-context middleware sets X-Request-ID on normal responses,
    # but an unhandled exception's response is built outside it.
    if error.request_id:
        headers = {**(headers or {}), "X-Request-ID": error.request_id}

    return ApiResponse(
        success=False,
        status_code=status_code,
        error=error,
        metadata=MetadataModel(request_id=error.request_id),
        headers=headers,
    )


def app_exception_handler(
    request: Request,
    exc: Exception,
) -> ApiResponse:
    """
    Handle expected application errors.

    Registered for AppError only; typed `Exception` because that is
    the handler signature Starlette accepts.
    """

    if not isinstance(exc, AppError):
        return unhandled_exception_handler(request, exc)

    logger.warning(
        "Application error.",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "error_message": exc.message,
        },
    )

    return _error_response(
        error=public_error(exc, request_id=_request_id(request)),
        status_code=exc.status_code,
        headers=exc.headers,
    )


def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> ApiResponse:
    """
    Handle unexpected exceptions.
    """

    logger.exception(
        "Unhandled application exception.",
    )

    return _error_response(
        error=public_error(exc, request_id=_request_id(request)),
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(
    app: FastAPI,
) -> None:
    """
    Register global exception handlers.
    """

    app.add_exception_handler(
        AppError,
        app_exception_handler,
    )

    app.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )
