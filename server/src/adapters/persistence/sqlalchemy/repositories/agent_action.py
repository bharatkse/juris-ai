"""
Agent action persistence repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, false, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.agent_action import AgentAction
from adapters.persistence.sqlalchemy.repositories.base import BaseRepository
from core.enums import AgentActionStatusEnum
from core.utils.datetime import utcnow


class AgentActionRepository(BaseRepository[AgentAction]):
    """
    SQLAlchemy persistence implementation for agent actions.

    The repository is responsible only for persistence and retrieval.

    It does not:
    - construct business entities,
    - calculate fingerprints,
    - authorize actions,
    - evaluate HITL policy,
    - create approvals,
    - execute actions,
    - convert entities to DTOs.
    """

    _model = AgentAction

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
        entity: AgentAction,
    ) -> AgentAction:
        """
        Persist and return an agent action entity.
        """

        await self.persist(
            entity,
        )

        return entity

    async def get(
        self,
        action_id: str,
    ) -> AgentAction | None:
        """
        Retrieve an agent action by ID.
        """

        statement = select(self._model).where(
            self._model.id == action_id,
        )

        result = await self._session.execute(
            statement,
        )

        return result.scalar_one_or_none()

    async def claim(
        self,
        action_id: str,
        *,
        from_statuses: frozenset[AgentActionStatusEnum],
        stale_before: datetime | None,
    ) -> bool:
        """
        Atomically move an action to EXECUTING, if it is in one of
        from_statuses or (only when stale_before is given) has been
        EXECUTING without an update since stale_before. True when this
        call made the change.

        One conditional UPDATE, so concurrent callers (in any worker)
        can't both win: Postgres re-checks the WHERE clause against the
        row a concurrent winner committed. The caller commits.
        """

        statement = (
            update(self._model)
            .where(
                self._model.id == action_id,
                or_(
                    self._model.status.in_(from_statuses),
                    and_(
                        self._model.status == AgentActionStatusEnum.EXECUTING,
                        self._model.updated_at < stale_before,
                    )
                    if stale_before is not None
                    else false(),
                ),
            )
            .values(
                status=AgentActionStatusEnum.EXECUTING,
                updated_at=utcnow(),
            )
            .returning(self._model.id)
        )

        result = await self._session.execute(
            statement,
        )

        return result.scalar_one_or_none() is not None

    async def get_by_execution(
        self,
        execution_id: str,
    ) -> list[AgentAction]:
        """
        Retrieve agent actions belonging to an execution.

        Results are ordered by creation time.
        """

        statement = (
            select(self._model)
            .where(
                self._model.execution_id == execution_id,
            )
            .order_by(
                self._model.created_at.asc(),
            )
        )

        result = await self._session.execute(
            statement,
        )

        return list(
            result.scalars().all(),
        )
