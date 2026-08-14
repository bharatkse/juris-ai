"""
Application entry point for the Juris-AI API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from src.api.exception_handlers import register_exception_handlers
from src.api.v1.routers import api_router
from src.core.config import get_settings
from src.core.constants import API_DESCRIPTION, API_TITLE
from src.core.file_system import ensure_dir
from src.core.logger import get_logger, setup_logging
from src.core.response import ApiResponse
from src.middleware.request_context import RequestContextMiddleware
from src.observability.telemetry import configure_telemetry, shutdown_telemetry

logger = get_logger(__name__)

settings = get_settings()


def initialize_logging() -> None:
    """
    Configure application logging.
    """

    setup_logging(
        level=settings.LOG_LEVEL,
        fmt=settings.LOG_FORMAT,
        log_file=settings.LOG_FILE,
        max_mb=settings.LOG_MAX_MB,
        backup_count=settings.LOG_BACKUP_COUNT,
    )


def initialize_storage() -> None:
    """
    Ensure required application directories exist.
    """

    for directory in (
        settings.DATA_DIRECTORY,
        settings.LOG_DIRECTORY,
    ):
        ensure_dir(directory)


def initialize_observability() -> None:
    """
    Configure application observability.
    """

    configure_telemetry()


async def startup() -> None:
    """
    Perform application startup tasks.
    """

    initialize_logging()

    logger.info(
        "Application starting.",
        extra={
            "application": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        },
    )

    initialize_storage()
    initialize_observability()

    #
    # Future initialization:
    #
    # - Database connectivity
    # - Database migrations
    # - Vector database
    # - AI model warm-up
    #

    logger.info(
        "Application started successfully.",
    )


async def shutdown() -> None:
    """
    Perform application shutdown tasks.
    """

    logger.info(
        "Application shutting down.",
    )


@asynccontextmanager
async def lifespan(
    _: FastAPI,
):
    """
    Manage the application lifecycle.
    """

    await startup()

    try:
        yield

    finally:
        await shutdown()
        shutdown_telemetry()


def configure_middleware(
    app: FastAPI,
) -> None:
    """
    Register application middleware.
    """

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        RequestContextMiddleware,
    )


def configure_routes(
    app: FastAPI,
) -> None:
    """
    Register API routes.
    """

    app.include_router(
        api_router,
    )

    @app.get(
        "/",
        include_in_schema=False,
    )
    async def root() -> ApiResponse:
        """
        Root endpoint.
        """

        return ApiResponse(
            success=True,
            data={
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "docs": ("/docs" if settings.ENABLE_DOCS else None),
                "health": "/api/v1/health",
            },
        )


def configure_instrumentation(
    app: FastAPI,
) -> None:
    """
    Configure framework-level OpenTelemetry instrumentation.
    """

    if not settings.OTEL_TRACING:
        return

    FastAPIInstrumentor.instrument_app(
        app,
    )


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url=("/docs" if settings.ENABLE_DOCS else None),
        redoc_url=("/redoc" if settings.ENABLE_DOCS else None),
        openapi_url=("/openapi.json" if settings.ENABLE_DOCS else None),
        lifespan=lifespan,
    )

    configure_middleware(
        app,
    )

    configure_instrumentation(
        app,
    )

    register_exception_handlers(
        app,
    )

    configure_routes(
        app,
    )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=(1 if settings.DEBUG else settings.WORKERS),
        log_level=settings.LOG_LEVEL.lower(),
    )
