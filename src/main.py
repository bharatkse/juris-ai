"""
Application entry point for the Juris-AI API.

This module is responsible for:
- Creating and configuring the FastAPI application
- Registering global exception handlers
- Including API routers
- Exposing a lightweight system health check endpoint

Run in development:
    uvicorn main:app --reload

Run in production:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2

"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.exception_handlers import register_exception_handlers
from src.api.v1.routers import api_router
from src.core.config import settings
from src.core.constants import API_DESCRIPTION, API_TITLE
from src.core.logger import get_logger, setup_logging
from src.core.utils.file_utils import ensure_dir
from src.frontend.router import router as frontend_router
from src.middleware.request_context import RequestContextMiddleware

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Everything in the `try` block runs at startup.
    Everything after `yield` runs at shutdown.
    """
    # 1. Configure logging
    setup_logging(
        level=settings.LOG_LEVEL,
        fmt=settings.LOG_FORMAT,
        log_file=settings.LOG_FILE,
        max_mb=settings.LOG_MAX_MB,
        backup_count=settings.LOG_BACKUP_COUNT,
    )

    log.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")

    # 2. Ensure required directories exist
    for path in [
        # settings.STORAGE_PATH,
        # settings.VECTOR_DB_PATH,
        "data/raw",
        "data/db",
        "logs",
    ]:
        ensure_dir(path)

    # 3. Create DB tables (idempotent)
    # create_all_tables(engine)

    # 4. Verify DB is reachable
    # if not run_health_check(engine):
    #     log.critical("Database health check failed — some tables may be missing")

    log.info("Startup complete — ready to accept requests")

    yield  # ← application is running

    log.info(f"Shutting down {settings.APP_NAME}")


def create_app() -> FastAPI:
    """
    Initialize and configure the FastAPI application.

    Responsibilities:
    - Configure structured logging
    - Register global exception handlers
    - Include API routers for all endpoints
    - Set service metadata (title, version, description)

    Returns:
        FastAPI: Fully configured FastAPI application instance
    """
    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/redoc" if settings.ENABLE_DOCS else None,
        openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
        lifespan=lifespan,
    )

    # configure CORS (if needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Configured Custom middleware (applied in REVERSE order)
    app.add_middleware(RequestContextMiddleware)

    # Configured Exception handlers
    register_exception_handlers(app)

    # API Routers
    app.include_router(api_router)

    # Mount Frontend Static Dir
    app.mount(
        "/static",
        StaticFiles(directory="src/frontend/static"),
        name="static",
    )

    # Frontend Routers
    app.include_router(frontend_router)

    # Root endpoint
    @app.get("/", include_in_schema=False)
    def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs" if settings.ENABLE_DOCS else "disabled",
            "health": "/api/v1/health",
        }

    return app


# Application instance used by ASGI server
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
