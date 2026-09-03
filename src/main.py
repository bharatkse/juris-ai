"""
Application entry point for the Juris-AI API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from adapters.observability.logger import get_logger, setup_logging
from adapters.observability.telemetry import configure_telemetry, shutdown_telemetry
from api.exception_handlers import register_exception_handlers
from api.middleware.request_context import RequestContextMiddleware
from api.utilities.api_response import ApiResponse
from api.v1.routers import api_router
from config.settings import get_settings
from core.constants import API_DESCRIPTION, API_TITLE
from core.utils.file_system import ensure_dir
from runtime.composition import create_ai_orchestrator

logger = get_logger(__name__)

settings = get_settings()


def initialize_logging() -> None:
    """
    Configure application logging.
    """

    setup_logging(
        level=settings.logging.LOG_LEVEL,
        fmt=settings.logging.LOG_FORMAT,
        log_file=settings.logging.LOG_FILE,
        max_mb=settings.logging.LOG_MAX_MB,
        backup_count=settings.logging.LOG_BACKUP_COUNT,
    )


def initialize_storage() -> None:
    """
    Ensure required application directories exist.
    """

    for directory in (
        settings.logging.PROCESS_DATA_DIRECTORY,
        settings.logging.LOG_DIRECTORY,
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
            "application": settings.app.APP_NAME,
            "version": settings.app.APP_VERSION,
            "environment": settings.app.ENVIRONMENT,
        },
    )

    initialize_storage()
    initialize_observability()

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
    app: FastAPI,
):
    """
    Manage application lifecycle and runtime resources.
    """

    await startup()

    try:
        async with AsyncPostgresSaver.from_conn_string(
            settings.langgraph_database_url,
        ) as checkpointer:
            await checkpointer.setup()

            app.state.ai_orchestrator = create_ai_orchestrator(
                checkpointer=checkpointer,
            )

            logger.info(
                "AI orchestrator initialized.",
            )

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
        allow_origins=settings.app.CORS_ORIGINS,
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
                "name": settings.app.APP_NAME,
                "version": settings.app.APP_VERSION,
                "environment": settings.app.ENVIRONMENT,
                "docs": ("/docs" if settings.app.ENABLE_DOCS else None),
                "health": "/api/v1/health",
            },
        )


def configure_instrumentation(
    app: FastAPI,
) -> None:
    """
    Configure framework-level OpenTelemetry instrumentation.
    """

    if not settings.app.OTEL_TRACING:
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
        version=settings.app.APP_VERSION,
        docs_url=("/docs" if settings.app.ENABLE_DOCS else None),
        redoc_url=("/redoc" if settings.app.ENABLE_DOCS else None),
        openapi_url=("/openapi.json" if settings.app.ENABLE_DOCS else None),
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
        host=settings.app.HOST,
        port=settings.app.PORT,
        reload=settings.app.DEBUG,
        workers=(1 if settings.app.DEBUG else settings.app.WORKERS),
        log_level=settings.logging.LOG_LEVEL.lower(),
    )
