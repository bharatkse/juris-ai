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
from redis.asyncio import Redis
from redis.exceptions import RedisError

from adapters.observability.logger import get_logger, setup_logging
from adapters.observability.telemetry import configure_telemetry, shutdown_telemetry
from api.exception_handlers import register_exception_handlers
from api.middleware.request_context import RequestContextMiddleware
from api.utilities.api_response import ApiResponse
from api.v1.routers import api_router
from config.settings import get_settings
from core.constants import API_DESCRIPTION, API_TITLE
from core.enums import CacheBackendEnum
from core.utils.file_system import ensure_dir
from wiring.composition import create_ai_orchestrator
from wiring.factories.agent_policies import seed_default_agent_policies

logger = get_logger(__name__)

settings = get_settings()

REDIS_CHECK_TIMEOUT_SECONDS = 5


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


async def check_redis() -> None:
    """
    Verify the configured Redis is reachable before serving traffic.

    Regression guard for REDIS_HOST/REDIS_PORT resolving to the wrong
    place -- a hardcoded "localhost" inside the api container is the
    container itself, not the redis service, and nothing surfaced it
    until the first request touched the cache. Not optional under
    CACHE_BACKEND=REDIS: the LLM-judge and embedding memoization call
    the cache with no fallback, so an unreachable Redis fails every
    guardrail-reviewed request. Fail fast at startup instead. Skipped
    for the in-memory backend, which never connects to Redis.
    """

    if settings.security.CACHE_BACKEND is not CacheBackendEnum.REDIS:
        return

    host = settings.security.REDIS_HOST
    port = settings.security.REDIS_PORT

    # Same URL wiring/factories/cache.py connects with, so this
    # exercises exactly the connection the cache will use.
    client = Redis.from_url(
        settings.security.REDIS_URL,
        socket_connect_timeout=REDIS_CHECK_TIMEOUT_SECONDS,
        socket_timeout=REDIS_CHECK_TIMEOUT_SECONDS,
    )

    try:
        await client.ping()

    except (RedisError, OSError) as exc:
        raise RuntimeError(
            f"Redis is unreachable at {host}:{port} "
            "(check REDIS_HOST/REDIS_PORT -- inside a container 'localhost' "
            "is the container itself, not the redis service)."
        ) from exc

    finally:
        await client.aclose()

    logger.info(
        "Redis connection verified.",
        extra={
            "operation": "check_redis",
            "host": host,
            "port": port,
        },
    )


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
    await check_redis()

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
        await seed_default_agent_policies()

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
