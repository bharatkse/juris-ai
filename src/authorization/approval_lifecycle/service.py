"""
Human approval lifecycle service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.authorization.approval_lifecycle.fingerprint import create_action_fingerprint
from src.authorization.approval_lifecycle.protocols import ApprovalLifecycle
from src.core.dto.action import ActionResponseDTO
from src.core.dto.approval import ApprovalRequestDTO, ApprovalResponseDTO
from src.core.enums import ApprovalStatusEnum
from src.core.exceptions.authorization import AuthorizationError
from src.core.logger import get_logger
from src.repositories.approval import ApprovalRepository

logger = get_logger(__name__)


class ApprovalLifecycleService(ApprovalLifecycle):
    """
    Manages the human approval lifecycle.

    This service owns approval lifecycle rules.
    Persistence is delegated to ApprovalRepository.

    It does not:
        - perform RBAC authorization,
        - authenticate users,
        - execute actions,
        - modify actions.
    """

    def __init__(
        self,
        *,
        repository: ApprovalRepository,
        approval_ttl_seconds: int = 900,
    ) -> None:
        if approval_ttl_seconds <= 0:
            raise ValueError(
                "Approval TTL must be greater than zero.",
            )

        self._repository = repository
        self._approval_ttl_seconds = approval_ttl_seconds

    async def create(
        self,
        *,
        action: ActionResponseDTO,
        requested_by: str,
    ) -> ApprovalResponseDTO:
        """
        Create and persist a waiting approval request.
        """

        logger.info(
            "Creating approval request.",
            extra={
                "action_id": action.action_id,
                "event_id": action.event_id,
                "requested_by": requested_by,
            },
        )

        try:
            now = datetime.now(UTC)

            approval = ApprovalRequestDTO(
                action_id=action.action_id,
                action_fingerprint=create_action_fingerprint(
                    action,
                ),
                requested_by=requested_by,
                status=ApprovalStatusEnum.WAITING,
                expires_at=now
                + timedelta(
                    seconds=self._approval_ttl_seconds,
                ),
            )

            result = await self._repository.create(
                approval,
            )

            logger.info(
                "Approval request created.",
                extra={
                    "approval_id": result.approval_id,
                    "action_id": result.action_id,
                    "requested_by": result.requested_by,
                },
            )

            return result

        except Exception:
            logger.exception(
                "Failed to create approval request.",
                extra={
                    "action_id": action.action_id,
                    "event_id": action.event_id,
                    "requested_by": requested_by,
                },
            )
            raise

    async def get(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Retrieve an approval request.
        """

        try:
            approval = await self._repository.get(
                approval_id,
            )

            if approval is None:
                raise AuthorizationError(
                    "Approval request was not found.",
                )

            return approval

        except AuthorizationError:
            logger.warning(
                "Approval request was not found.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception:
            logger.exception(
                "Failed to retrieve approval request.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

    async def validate(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Validate that an approval is currently executable.

        Validation succeeds only when the approval:
            - exists,
            - has not expired,
            - is APPROVED.
        """

        logger.info(
            "Validating approval request.",
            extra={
                "approval_id": approval_id,
            },
        )

        try:
            approval = await self.get(
                approval_id,
            )

            if approval.is_expired:
                await self._expire(
                    approval,
                )

                raise AuthorizationError(
                    "Approval has expired.",
                )

            if not approval.is_approved:
                raise AuthorizationError(
                    "Approval is not valid for execution: " f"{approval.status}.",
                )

            logger.info(
                "Approval request validated.",
                extra={
                    "approval_id": approval.approval_id,
                    "action_id": approval.action_id,
                    "status": approval.status,
                },
            )

            return approval

        except AuthorizationError:
            logger.warning(
                "Approval validation failed.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception:
            logger.exception(
                "Failed to validate approval request.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

    async def approve(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Approve a waiting approval request.
        """

        logger.info(
            "Approving approval request.",
            extra={
                "approval_id": approval_id,
            },
        )

        try:
            approval = await self._require_waiting(
                approval_id,
            )

            result = await self._repository.update_status(
                approval_id=approval.approval_id,
                status=ApprovalStatusEnum.APPROVED,
            )

            logger.info(
                "Approval request approved.",
                extra={
                    "approval_id": result.approval_id,
                    "action_id": result.action_id,
                    "status": result.status,
                },
            )

            return result

        except AuthorizationError:
            logger.warning(
                "Approval request could not be approved.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception:
            logger.exception(
                "Failed to approve approval request.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

    async def reject(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Reject a waiting approval request.
        """

        logger.info(
            "Rejecting approval request.",
            extra={
                "approval_id": approval_id,
            },
        )

        try:
            approval = await self._require_waiting(
                approval_id,
            )

            result = await self._repository.update_status(
                approval_id=approval.approval_id,
                status=ApprovalStatusEnum.REJECTED,
            )

            logger.info(
                "Approval request rejected.",
                extra={
                    "approval_id": result.approval_id,
                    "action_id": result.action_id,
                    "status": result.status,
                },
            )

            return result

        except AuthorizationError:
            logger.warning(
                "Approval request could not be rejected.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception:
            logger.exception(
                "Failed to reject approval request.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

    async def edit(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Invalidate a waiting approval because the action
        is going to be changed.

        A changed action requires a new approval cycle.
        """

        logger.info(
            "Editing approval request.",
            extra={
                "approval_id": approval_id,
            },
        )

        try:
            approval = await self._require_waiting(
                approval_id,
            )

            result = await self._repository.update_status(
                approval_id=approval.approval_id,
                status=ApprovalStatusEnum.EDITED,
            )

            logger.info(
                "Approval request marked as edited.",
                extra={
                    "approval_id": result.approval_id,
                    "action_id": result.action_id,
                    "status": result.status,
                },
            )

            return result

        except AuthorizationError:
            logger.warning(
                "Approval request could not be edited.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception:
            logger.exception(
                "Failed to edit approval request.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

    async def _require_waiting(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Ensure an approval is still actionable.
        """

        approval = await self.get(
            approval_id,
        )

        if approval.is_expired:
            await self._expire(
                approval,
            )

            raise AuthorizationError(
                "Approval has expired.",
            )

        if not approval.is_waiting:
            raise AuthorizationError(
                "Approval is not actionable: " f"{approval.status}.",
            )

        return approval

    async def _expire(
        self,
        approval: ApprovalResponseDTO,
    ) -> ApprovalResponseDTO:
        """
        Persist the expired state.
        """

        logger.info(
            "Approval request expired.",
            extra={
                "approval_id": approval.approval_id,
                "action_id": approval.action_id,
            },
        )

        return await self._repository.update_status(
            approval_id=approval.approval_id,
            status=ApprovalStatusEnum.EXPIRED,
        )
