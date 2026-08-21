"""
Approval API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies.approval import get_approval_lifecycle_service
from src.api.dependencies.auth import get_current_user
from src.api.schemas.approval import ApprovalDecisionRequest, ApprovalResponse
from src.core.dto.approval import ApprovalDecisionRequestDTO
from src.core.exceptions.authorization import AuthorizationError
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.services.approval_lifecycle import ApprovalLifecycleService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"],
)


@router.post(
    "/{approval_id}",
    response_model=None,
    summary="Process approval request",
    status_code=status.HTTP_200_OK,
)
async def process_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    current_user=Depends(get_current_user),
    service: ApprovalLifecycleService = Depends(
        get_approval_lifecycle_service,
    ),
) -> ApiResponse:
    """
    Process a human decision for an approval request.
    """

    logger.info(
        "Processing approval request.",
        extra={
            "operation": "process_approval",
            "approval_id": approval_id,
            "decision": request.decision.value,
            "user_id": str(current_user.id),
        },
    )

    try:
        result = await service.process(
            approval_id=approval_id,
            request=ApprovalDecisionRequestDTO(
                decision=request.decision,
                edited_payload=request.edited_payload,
                decision_reason=request.decision_reason,
            ),
            user_id=current_user.id,
        )
        return ApiResponse(
            success=True,
            status_code=status.HTTP_200_OK,
            data=ApprovalResponse.model_validate(
                result,
                from_attributes=True,
            ),
        )

    except AuthorizationError:
        logger.warning(
            "Approval request could not be processed.",
            extra={
                "operation": "process_approval",
                "approval_id": approval_id,
                "decision": request.decision.value,
                "user_id": str(current_user.id),
            },
            exc_info=True,
        )
        raise

    except Exception:
        logger.exception(
            "Approval request processing failed.",
            extra={
                "operation": "process_approval",
                "approval_id": approval_id,
                "decision": request.decision.value,
                "user_id": str(current_user.id),
            },
        )
        raise
