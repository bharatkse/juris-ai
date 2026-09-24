"""
Health API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from adapters.observability.logger import get_logger
from adapters.observability.metrics import metrics
from api.dependencies.context import get_request_context
from api.utilities.api_response import ApiResponse
from application.context.request import RequestContext
from config.settings import get_settings

logger = get_logger(__name__)

settings = get_settings()

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get(
    "",
    summary="Health check endpoint",
    status_code=status.HTTP_200_OK,
)
async def health(
    context: RequestContext = Depends(
        get_request_context,
    ),
) -> ApiResponse:
    """
    Return the application health status.
    """

    metrics.health_checks.add(1)

    logger.info(
        "Health check requested.",
        extra={
            "operation": "health_check",
        },
    )

    return ApiResponse(
        success=True,
        status_code=status.HTTP_200_OK,
        data={
            "status": "healthy",
            "service": settings.app.APP_NAME,
            "version": settings.app.APP_VERSION,
            "environment": settings.app.ENVIRONMENT,
        },
        metadata=context.to_metadata(),
    )
