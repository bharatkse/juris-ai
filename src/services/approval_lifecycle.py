"""
Human approval lifecycle application service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.authorization.approval_lifecycle.protocols import ApprovalLifecycleProtocol
from src.core.dto.agent_action import AgentActionResponseDTO
from src.core.dto.approval import (
    ApprovalDecisionRequestDTO,
    ApprovalRequestDTO,
    ApprovalResponseDTO,
)
from src.core.enums import ApprovalDecisionEnum, ApprovalStatusEnum
from src.core.exceptions.approval import (
    ApprovalError,
    ApprovalExpiredError,
    ApprovalNotActionableError,
    ApprovalNotFoundError,
    ApprovalValidationError,
)
from src.core.logger import get_logger
from src.db.models.approval import Approval
from src.repositories.approval import ApprovalRepository

logger = get_logger(__name__)


class ApprovalLifecycleService(ApprovalLifecycleProtocol):
    """
    Application service for the complete human approval lifecycle.

    Responsibilities:
    - create approval requests,
    - retrieve approvals,
    - validate approvals,
    - process human decisions,
    - approve waiting requests,
    - reject waiting requests,
    - edit waiting requests,
    - expire invalid approvals.

    It does not:
    - perform RBAC authorization,
    - evaluate approval policy,
    - authenticate users,
    - execute actions,
    - modify AgentActions directly.
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
        action: AgentActionResponseDTO,
        requested_by: str,
    ) -> ApprovalResponseDTO:
        """
        Create and persist a waiting approval request.
        """

        try:
            now = datetime.now(UTC)

            request = ApprovalRequestDTO(
                agent_action_id=action.action_id,
                requested_by=requested_by,
                expires_at=now
                + timedelta(
                    seconds=self._approval_ttl_seconds,
                ),
            )

            entity = Approval.from_dto(
                approval=request,
            )

            persisted = await self._repository.create(
                entity=entity,
            )

            logger.info(
                "Approval request created.",
                extra={
                    "approval_id": persisted.id,
                    "agent_action_id": persisted.agent_action_id,
                    "requested_by": requested_by,
                },
            )

            return persisted.to_dto()

        except ApprovalError:
            logger.exception(
                "Approval request creation failed.",
                extra={
                    "action_id": action.action_id,
                    "requested_by": requested_by,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while creating approval request.",
                extra={
                    "action_id": action.action_id,
                    "requested_by": requested_by,
                },
            )

            raise ApprovalError(
                "Failed to create approval request.",
            ) from exc

    async def get(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Retrieve an approval request.
        """

        try:
            entity = await self._get_entity(
                approval_id,
            )

            return entity.to_dto()

        except ApprovalNotFoundError:
            logger.warning(
                "Approval request not found.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except ApprovalError:
            logger.exception(
                "Approval request retrieval failed.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while retrieving approval request.",
                extra={
                    "approval_id": approval_id,
                },
            )

            raise ApprovalError(
                "Failed to retrieve approval request.",
            ) from exc

    async def validate(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Validate that an approval is currently executable.
        """

        try:
            entity = await self._get_entity(
                approval_id,
            )

            if entity.is_expired:
                await self._expire(
                    entity,
                )

                raise ApprovalExpiredError(
                    "Approval has expired.",
                )

            if entity.status != ApprovalStatusEnum.APPROVED:
                raise ApprovalValidationError(
                    "Approval is not valid for execution: " f"{entity.status.value}.",
                )

            logger.info(
                "Approval validated for execution.",
                extra={
                    "approval_id": entity.id,
                    "agent_action_id": entity.agent_action_id,
                },
            )

            return entity.to_dto()

        except (
            ApprovalNotFoundError,
            ApprovalExpiredError,
            ApprovalValidationError,
        ):
            logger.warning(
                "Approval validation failed.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except ApprovalError:
            logger.exception(
                "Approval validation failed unexpectedly.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while validating approval.",
                extra={
                    "approval_id": approval_id,
                },
            )

            raise ApprovalError(
                "Failed to validate approval request.",
            ) from exc

    async def process(
        self,
        *,
        approval_id: str,
        request: ApprovalDecisionRequestDTO,
        user_id: str,
    ) -> ApprovalResponseDTO:
        """
        Process a human approval decision.

        This is the application-facing entry point for approval
        decisions.
        """

        try:
            if request.decision == ApprovalDecisionEnum.APPROVE:
                return await self.approve(
                    approval_id=approval_id,
                    user_id=user_id,
                    decision_reason=request.decision_reason,
                )

            if request.decision == ApprovalDecisionEnum.REJECT:
                return await self.reject(
                    approval_id=approval_id,
                    user_id=user_id,
                    decision_reason=request.decision_reason,
                )

            if request.decision == ApprovalDecisionEnum.EDIT:
                return await self.edit(
                    approval_id=approval_id,
                    user_id=user_id,
                    edited_payload=request.edited_payload,
                    decision_reason=request.decision_reason,
                )

            raise ApprovalValidationError(
                f"Unsupported approval decision: {request.decision}.",
            )

        except ApprovalError:
            logger.exception(
                "Approval decision processing failed.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                    "decision": request.decision.value,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while processing approval decision.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                    "decision": request.decision.value,
                },
            )

            raise ApprovalError(
                "Failed to process approval decision.",
            ) from exc

    async def approve(
        self,
        *,
        approval_id: str,
        user_id: str,
        decision_reason: str | None = None,
    ) -> ApprovalResponseDTO:
        """
        Approve a waiting approval request.
        """

        try:
            entity = await self._get_waiting_entity(
                approval_id,
            )

            entity.status = ApprovalStatusEnum.APPROVED
            entity.approved_by = user_id
            entity.decision_type = ApprovalDecisionEnum.APPROVE
            entity.decision_reason = decision_reason
            entity.decided_at = datetime.now(UTC)

            return await self._save_decision(
                entity=entity,
                user_id=user_id,
            )

        except ApprovalError:
            logger.exception(
                "Failed to approve approval request.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while approving approval request.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                },
            )

            raise ApprovalError(
                "Failed to approve approval request.",
            ) from exc

    async def reject(
        self,
        *,
        approval_id: str,
        user_id: str,
        decision_reason: str | None = None,
    ) -> ApprovalResponseDTO:
        """
        Reject a waiting approval request.
        """

        try:
            entity = await self._get_waiting_entity(
                approval_id,
            )

            entity.status = ApprovalStatusEnum.REJECTED
            entity.approved_by = user_id
            entity.decision_type = ApprovalDecisionEnum.REJECT
            entity.decision_reason = decision_reason
            entity.decided_at = datetime.now(UTC)

            return await self._save_decision(
                entity=entity,
                user_id=user_id,
            )

        except ApprovalError:
            logger.exception(
                "Failed to reject approval request.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while rejecting approval request.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                },
            )

            raise ApprovalError(
                "Failed to reject approval request.",
            ) from exc

    async def edit(
        self,
        *,
        approval_id: str,
        user_id: str,
        edited_payload: dict[str, Any] | None = None,
        decision_reason: str | None = None,
    ) -> ApprovalResponseDTO:
        """
        Mark a waiting approval request as edited.

        The current approval cycle becomes invalid.
        A new approval cycle is required for the changed action.
        """

        try:
            entity = await self._get_waiting_entity(
                approval_id,
            )

            entity.status = ApprovalStatusEnum.EDITED
            entity.approved_by = user_id
            entity.decision_type = ApprovalDecisionEnum.EDIT
            entity.decision_reason = decision_reason
            entity.edited_payload = edited_payload
            entity.decided_at = datetime.now(UTC)

            return await self._save_decision(
                entity=entity,
                user_id=user_id,
            )

        except ApprovalError:
            logger.exception(
                "Failed to edit approval request.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while editing approval request.",
                extra={
                    "approval_id": approval_id,
                    "user_id": user_id,
                },
            )

            raise ApprovalError(
                "Failed to edit approval request.",
            ) from exc

    async def _get_entity(
        self,
        approval_id: str,
    ) -> Approval:
        """
        Retrieve an approval entity.
        """

        try:
            entity = await self._repository.get(
                approval_id,
            )

            if entity is None:
                raise ApprovalNotFoundError(
                    "Approval request was not found.",
                )

            return entity

        except ApprovalNotFoundError:
            raise

        except ApprovalError:
            raise

        except Exception as exc:
            logger.exception(
                "Failed to retrieve approval entity.",
                extra={
                    "approval_id": approval_id,
                },
            )

            raise ApprovalError(
                "Failed to retrieve approval request.",
            ) from exc

    async def _get_waiting_entity(
        self,
        approval_id: str,
    ) -> Approval:
        """
        Retrieve an approval that is still actionable.
        """

        try:
            entity = await self._get_entity(
                approval_id,
            )

            if entity.is_expired:
                await self._expire(
                    entity,
                )

                raise ApprovalExpiredError(
                    "Approval has expired.",
                )

            if entity.status != ApprovalStatusEnum.WAITING:
                raise ApprovalNotActionableError(
                    "Approval is not actionable: " f"{entity.status.value}.",
                )

            return entity

        except (
            ApprovalNotFoundError,
            ApprovalExpiredError,
            ApprovalNotActionableError,
        ):
            raise

        except ApprovalError:
            logger.exception(
                "Failed to resolve waiting approval.",
                extra={
                    "approval_id": approval_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while resolving waiting approval.",
                extra={
                    "approval_id": approval_id,
                },
            )

            raise ApprovalError(
                "Failed to resolve approval request.",
            ) from exc

    async def _save_decision(
        self,
        *,
        entity: Approval,
        user_id: str,
    ) -> ApprovalResponseDTO:
        """
        Persist an approval decision.
        """

        try:
            persisted = await self._repository.save(
                entity=entity,
            )

            logger.info(
                "Approval decision persisted.",
                extra={
                    "approval_id": persisted.id,
                    "agent_action_id": persisted.agent_action_id,
                    "decision": (
                        persisted.decision_type.value if persisted.decision_type else None
                    ),
                    "user_id": user_id,
                },
            )

            return persisted.to_dto()

        except ApprovalError:
            logger.exception(
                "Approval decision persistence failed.",
                extra={
                    "approval_id": entity.id,
                    "user_id": user_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while persisting approval decision.",
                extra={
                    "approval_id": entity.id,
                    "user_id": user_id,
                },
            )

            raise ApprovalError(
                "Failed to persist approval decision.",
            ) from exc

    async def _expire(
        self,
        entity: Approval,
    ) -> ApprovalResponseDTO:
        """
        Persist the expired state.
        """

        try:
            entity.status = ApprovalStatusEnum.EXPIRED

            persisted = await self._repository.save(
                entity=entity,
            )

            logger.info(
                "Approval request expired.",
                extra={
                    "approval_id": persisted.id,
                    "agent_action_id": persisted.agent_action_id,
                },
            )

            return persisted.to_dto()

        except ApprovalError:
            logger.exception(
                "Approval expiration failed.",
                extra={
                    "approval_id": entity.id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while expiring approval request.",
                extra={
                    "approval_id": entity.id,
                },
            )

            raise ApprovalError(
                "Failed to expire approval request.",
            ) from exc
