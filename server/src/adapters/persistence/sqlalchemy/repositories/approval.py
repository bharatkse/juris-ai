"""
Approval persistence repository.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.approval import Approval
from adapters.persistence.sqlalchemy.repositories.base import BaseRepository
from core.enums import ApprovalStatusEnum


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

    async def save_decision(
        self,
        *,
        entity: Approval,
    ) -> bool:
        """
        Write the decision set on entity, only if the approval is still
        WAITING in the database. True when this call recorded it.

        One conditional UPDATE, so of two concurrent decisions (approve
        and reject, in any workers) only one is recorded: Postgres
        re-checks the WHERE clause against the row a concurrent winner
        committed. Either way entity is reloaded from the row afterwards:
        the recorded decision, or on False the decision that won (its
        own unwritten changes are discarded). The caller commits.
        """

        statement = (
            update(self._model)
            .where(
                self._model.id == entity.id,
                self._model.status == ApprovalStatusEnum.WAITING,
            )
            .values(
                status=entity.status,
                approved_by=entity.approved_by,
                decision_type=entity.decision_type,
                decision_reason=entity.decision_reason,
                edited_payload=entity.edited_payload,
                decided_at=entity.decided_at,
            )
            .returning(self._model.id)
        )

        result = await self._session.execute(
            statement,
        )
        recorded = result.scalar_one_or_none() is not None

        await self._session.refresh(entity)

        return recorded
