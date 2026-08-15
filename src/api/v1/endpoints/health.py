"""
Health API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies.context import get_request_context
from src.core.config import get_settings
from src.core.context import RequestContext
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.observability.metrics import metrics

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
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        },
        metadata=context.to_metadata(),
    )
