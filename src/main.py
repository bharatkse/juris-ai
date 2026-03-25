"""
Application entry point for the Charging Station Hygiene Service.

This module is responsible for:
- Creating and configuring the FastAPI application
- Registering global exception handlers
- Including API routers
- Exposing a lightweight system health check endpoint
"""

from fastapi import FastAPI

from src.config import settings
from src.core.exception_handlers import register_exception_handlers
from src.core.logger import configure_logging
from src.routes import users


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
    # Configure structured logging before the app starts
    configure_logging()

    fastapi_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description=(
            "Service for ingesting health reports and computing "
            "hygiene scores for charging stations."
        ),
    )

    # Attach global exception handlers to the app
    register_exception_handlers(fastapi_app)

    # Include API routers
    fastapi_app.include_router(users.router)

    return fastapi_app


# Application instance used by ASGI server
app = create_app()


@app.get("/health", tags=["System"])
def system_health_check() -> dict[str, str]:
    """
    Lightweight system health check endpoint.

    This endpoint is intended for use by:
    - Docker healthcheck commands
    - Kubernetes liveness and readiness probes
    - Load balancers or monitoring tools

    Returns:
        dict: Simple status response indicating service is running
    """
    return {"status": "ok"}
