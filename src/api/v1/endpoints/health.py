from fastapi import APIRouter, Depends

from src.api.dependencies.context import get_request_context
from src.core.config import get_settings
from src.core.context import RequestContext
from src.core.response import ApiResponse

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)

settings = get_settings()


@router.get("", summary="Health check endpoint")
async def health(
    context: RequestContext = Depends(get_request_context),
):
    data = {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }

    return ApiResponse(success=True, data=data, status_code=200, metadata=context.to_metadata())
