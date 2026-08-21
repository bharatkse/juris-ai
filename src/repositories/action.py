"""
Action persistence repository.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dto.action import ActionRequestDTO, ActionResponseDTO
from src.db.models.action import Action
from src.repositories.base import BaseRepository


class ActionRepository(
    BaseRepository[Action],
):
    """
    SQLAlchemy persistence implementation for actions.

    Persistence concerns only.
    Action lifecycle rules remain outside the repository.
    """

    _model = Action

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
        event_id: str,
        action: ActionRequestDTO,
    ) -> ActionResponseDTO:
        """
        Persist a new action.
        """

        entity = Action(
            event_id=event_id,
            tool_name=action.tool_name,
            action_type=action.action_type,
            agent_id=action.agent_id,
            arguments=action.arguments,
            reason=action.reason,
            resource_id=action.resource_id,
        )

        await self.persist(
            entity,
        )

        return self._to_dto(
            entity,
        )

    async def get(
        self,
        action_id: str,
    ) -> ActionResponseDTO | None:
        """
        Retrieve an action by ID.
        """

        statement = self.active_select().where(
            self._model.id == action_id,
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

    @staticmethod
    def _to_dto(
        entity: Action,
    ) -> ActionResponseDTO:
        """
        Convert a persisted action into its response DTO.
        """

        return ActionResponseDTO(
            action_id=entity.id,
            event_id=entity.event_id,
            tool_name=entity.tool_name,
            action_type=entity.action_type,
            agent_id=entity.agent_id,
            arguments=entity.arguments,
            reason=entity.reason,
            resource_id=entity.resource_id,
        )
