"""
Approval persistence repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.approval import Approval
from src.repositories.base import BaseRepository


class ApprovalRepository(
    BaseRepository[Approval],
):
    """
    SQLAlchemy persistence implementation for approvals.

    Responsibilities:
    - persist approval entities,
    - retrieve approval entities,
    - save changes to approval entities.

    It does not:
    - implement approval lifecycle rules,
    - validate approval state,
    - decide approval/rejection,
    - handle expiry,
    - convert entities to DTOs.
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
        *,
        entity: Approval,
    ) -> Approval:
        """
        Persist and return a new approval entity.
        """

        await self.persist(
            entity,
        )

        return entity

    async def get(
        self,
        approval_id: str,
    ) -> Approval | None:
        """
        Retrieve an approval by ID.
        """

        statement = select(self._model).where(
            self._model.id == approval_id,
        )

        result = await self._session.execute(
            statement,
        )

        return result.scalar_one_or_none()

    async def save(
        self,
        *,
        entity: Approval,
    ) -> Approval:
        """
        Persist changes to an existing approval entity.

        Lifecycle/state validation remains in
        ApprovalLifecycleService.
        """

        await self.flush()

        return entity
