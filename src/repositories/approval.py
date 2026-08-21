"""
Approval persistence repository.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dto.approval import ApprovalRequestDTO, ApprovalResponseDTO
from src.core.enums import ApprovalStatusEnum
from src.db.models.approval import Approval
from src.repositories.base import BaseRepository


class ApprovalRepository(
    BaseRepository[Approval],
):
    """
    SQLAlchemy persistence implementation for approval requests.

    Persistence concerns only.
    Approval lifecycle rules remain in ApprovalLifecycleService.
    """

    _model = Approval

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        super().__init__(
            session=session,
        )

    async def create(
        self,
        approval: ApprovalRequestDTO,
    ) -> ApprovalResponseDTO:
        """
        Persist a new approval request.
        """

        entity = Approval(
            action_id=approval.action_id,
            action_fingerprint=approval.action_fingerprint,
            requested_by=approval.requested_by,
            status=approval.status,
            expires_at=approval.expires_at,
        )

        await self.persist(
            entity,
        )

        return self._to_dto(
            entity,
        )

    async def get(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO | None:
        """
        Retrieve an approval request by ID.
        """

        statement = self.active_select().where(
            self._model.id == approval_id,
        )

        result = await self._session.execute(
            statement,
        )

        entity = result.scalar_one_or_none()

        if entity is None:
            return None

        return self._to_dto(
            entity,
        )

    async def update_status(
        self,
        *,
        approval_id: str,
        status: ApprovalStatusEnum,
    ) -> ApprovalResponseDTO:
        """
        Persist an approval status transition.
        """

        statement = self.active_select().where(
            self._model.id == approval_id,
        )

        result = await self._session.execute(
            statement,
        )

        entity = result.scalar_one_or_none()

        if entity is None:
            raise LookupError(
                f"Approval request not found: {approval_id}",
            )

        entity.status = status

        await self.flush()

        await self.refresh(
            entity,
        )

        return self._to_dto(
            entity,
        )

    @staticmethod
    def _to_dto(
        entity: Approval,
    ) -> ApprovalResponseDTO:
        """
        Convert a persisted approval into its response DTO.
        """

        return ApprovalResponseDTO(
            approval_id=entity.id,
            action_id=entity.action_id,
            action_fingerprint=entity.action_fingerprint,
            requested_by=entity.requested_by,
            status=entity.status,
            created_at=entity.created_at,
            expires_at=entity.expires_at,
        )
