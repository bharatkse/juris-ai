"""
Agent action application service.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.authorization.approval_lifecycle.fingerprint import create_action_fingerprint
from src.core.dto.agent_action import AgentActionRequestDTO
from src.core.exceptions.agent_action import AgentActionError
from src.core.logger import get_logger
from src.db.models.agent_action import AgentAction
from src.repositories.agent_action import AgentActionRepository
from src.services.base import BaseService

logger = get_logger(__name__)


class AgentActionService(BaseService):
    """
    Application service for AgentAction persistence and lifecycle.

    Responsibilities:
    - Create concrete AgentAction records.
    - Generate action fingerprints.
    - Construct AgentAction entities.
    - Manage AgentAction lifecycle transitions.

    It does not:
    - authorize actions,
    - evaluate HITL policy,
    - create approvals,
    - execute actions.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: AgentActionRepository,
    ) -> None:
        super().__init__(session)
        self._repository = repository

    async def create(
        self,
        *,
        action: AgentActionRequestDTO,
        user_id: str,
        tenant_id: str,
    ) -> AgentAction:
        """
        Create and persist a concrete AgentAction.

        Entity construction belongs to the application/model layer.
        The repository receives an already-constructed entity and
        performs persistence only.
        """

        try:
            fingerprint = create_action_fingerprint(
                action,
            )

            entity = AgentAction.from_dto(
                action=action,
                user_id=user_id,
                tenant_id=tenant_id,
                fingerprint=fingerprint,
            )

            entity = await self._repository.create(
                entity=entity,
            )

            logger.info(
                "Agent action created",
                extra={
                    "action_id": entity.id,
                    "execution_id": entity.execution_id,
                    "agent_id": entity.agent_id,
                    "action_type": entity.action_type.value,
                    "actor_type": entity.actor_type.value,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                },
            )

            return entity

        except AgentActionError:
            logger.exception(
                "Agent action creation failed",
                extra={
                    "execution_id": action.execution_id,
                    "agent_id": action.agent_id,
                    "action_type": action.action_type.value,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error while creating agent action",
                extra={
                    "execution_id": action.execution_id,
                    "agent_id": action.agent_id,
                    "action_type": action.action_type.value,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                },
            )

            raise AgentActionError(
                "Failed to create agent action.",
            ) from exc
