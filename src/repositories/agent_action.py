"""
Agent action persistence repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.agent_action import AgentAction
from src.repositories.base import BaseRepository


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
