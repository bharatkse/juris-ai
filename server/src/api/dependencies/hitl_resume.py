"""
HITL resume API dependencies.
"""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from adapters.persistence.sqlalchemy.session import get_db_session
from agentic.orchestration.orchestrator import AIOrchestrator
from api.dependencies.action_workflow import get_action_workflow_service
from api.dependencies.agent_action import get_agent_action_repository
from api.dependencies.chat import get_conversation_event_service
from api.dependencies.user_memory import get_memory_extraction_scheduler
from application.services.action_workflow import ActionWorkflowService
from application.services.conversation_event import ConversationEventService
from application.services.hitl_resume import HitlResumeService
from application.services.user_memory_extraction import MemoryExtractionScheduler


def get_hitl_ai_orchestrator(
    request: Request,
) -> AIOrchestrator:
    """
    Return the application-scoped AI orchestrator.

    Duplicated (rather than imported) from api.dependencies.chat to
    avoid a chat.py <-> hitl_resume.py import cycle; both simply
    return request.app.state.ai_orchestrator.
    """

    return request.app.state.ai_orchestrator


def get_hitl_resume_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    agent_action_repository: AgentActionRepository = Depends(
        get_agent_action_repository,
    ),
    conversation_event_service: ConversationEventService = Depends(
        get_conversation_event_service,
    ),
    orchestrator: AIOrchestrator = Depends(
        get_hitl_ai_orchestrator,
    ),
    action_workflow_service: ActionWorkflowService = Depends(
        get_action_workflow_service,
    ),
    memory_extraction_scheduler: MemoryExtractionScheduler = Depends(
        get_memory_extraction_scheduler,
    ),
) -> HitlResumeService:
    """
    Create the request-scoped HITL resume service.
    """

    return HitlResumeService(
        session=session,
        agent_action_repository=agent_action_repository,
        conversation_event_service=conversation_event_service,
        orchestrator=orchestrator,
        action_workflow_service=action_workflow_service,
        memory_extraction_scheduler=memory_extraction_scheduler,
    )
