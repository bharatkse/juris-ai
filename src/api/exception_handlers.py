"""
Global exception handlers.
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from src.core.constants import (
    ERROR_INTERNAL_SERVER_ERROR,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from src.core.exceptions.base import AppError
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.schemas.base import ErrorDetailModel

logger = get_logger(__name__)


def app_exception_handler(
    _: Request,
    exc: AppError,
) -> ApiResponse:
    """
    Handle expected application errors.
    """

    logger.warning(
        "Application error.",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "message": exc.message,
        },
    )

    return ApiResponse(
        success=False,
        status_code=exc.status_code,
        error=ErrorDetailModel(
            code=exc.error_code,
            message=exc.message,
        ),
    )


def unhandled_exception_handler(
    _: Request,
    exc: Exception,
) -> ApiResponse:
    """
    Handle unexpected exceptions.
    """

    logger.exception(
        "Unhandled application exception.",
    )

    return ApiResponse(
        success=False,
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        error=ErrorDetailModel(
            code=ERROR_INTERNAL_SERVER_ERROR,
            message=("An unexpected error occurred. " "Please try again later."),
        ),
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
