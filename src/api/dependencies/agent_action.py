"""
Agent action API dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.repositories.agent_action import AgentActionRepository
from src.services.agent_action import AgentActionService


def get_agent_action_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> AgentActionRepository:
    """
    Create an agent action repository.
    """

    return AgentActionRepository(
        session=session,
    )


def get_agent_action_service(
    repository: AgentActionRepository = Depends(
        get_agent_action_repository,
    ),
) -> AgentActionService:
    """
    Create an agent action application service.
    """

    return AgentActionService(
        repository=repository,
    )
