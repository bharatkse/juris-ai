"""
Approval application service.
"""

from __future__ import annotations

from src.authorization.approval_lifecycle.service import ApprovalLifecycleService
from src.core.dto.approval import ApprovalResponseDTO
from src.core.enums import ApprovalStatusEnum


class ApprovalService(ApprovalLifecycleService):
    """
    Application-facing approval service.

    Extends the approval lifecycle service with API-level
    approval processing.

    Lifecycle rules remain owned by ApprovalLifecycleService.
    """

    async def process(
        self,
        *,
        approval_id: str,
        action: ApprovalStatusEnum,
        user_id: str,
    ) -> ApprovalResponseDTO:
        """
        Process a human decision for an approval request.
        """

        # TODO: verify that user_id is allowed to make
        # the decision for this approval.

        if action == ApprovalStatusEnum.APPROVED:
            return await self.approve(
                approval_id,
            )

        if action == ApprovalStatusEnum.REJECTED:
            return await self.reject(
                approval_id,
            )

        if action == ApprovalStatusEnum.EDITED:
            return await self.edit(
                approval_id,
            )

        raise ValueError(
            f"Unsupported approval decision: {action}",
        )
