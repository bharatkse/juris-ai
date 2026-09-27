"""
User memory dependencies.
"""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.user import UserRepository
from adapters.persistence.sqlalchemy.repositories.user_memory import (
    UserMemoryRepository,
)
from adapters.persistence.sqlalchemy.session import get_db_session
from api.dependencies.compliance_log import get_compliance_log_service
from api.dependencies.conversation import get_conversation_repository
from api.dependencies.user import get_user_repository
from application.services.compliance_log import ComplianceLogService
from application.services.user_memory import UserMemoryService
from application.services.user_memory_extraction import MemoryExtractionScheduler
from rag.protocols.embedding_provider import EmbeddingProviderProtocol


def get_embedding_provider(
    request: Request,
) -> EmbeddingProviderProtocol:
    """
    Return the application-scoped embedding provider.

    Set once at startup (main.py's lifespan) from the same
    ClientContainer the orchestrator uses, so the embedding model is
    loaded exactly once for the whole process.
    """

    embedding_provider: EmbeddingProviderProtocol = request.app.state.embedding_provider

    return embedding_provider


def get_memory_extraction_scheduler(
    request: Request,
) -> MemoryExtractionScheduler:
    """
    Return the application-scoped memory extraction scheduler.

    Built once at startup (main.py's lifespan): it tracks the
    in-flight background runs, so it must be a single shared instance.
    """

    scheduler: MemoryExtractionScheduler = request.app.state.memory_extraction_scheduler

    return scheduler


def get_user_memory_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> UserMemoryRepository:
    """
    Create a UserMemoryRepository.
    """

    return UserMemoryRepository(
        session=session,
    )


def get_user_memory_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    repository: UserMemoryRepository = Depends(
        get_user_memory_repository,
    ),
    user_repository: UserRepository = Depends(
        get_user_repository,
    ),
    conversation_repository: ConversationRepository = Depends(
        get_conversation_repository,
    ),
    embedding_provider: EmbeddingProviderProtocol = Depends(
        get_embedding_provider,
    ),
    compliance_log: ComplianceLogService = Depends(
        get_compliance_log_service,
    ),
) -> UserMemoryService:
    """
    Create a UserMemoryService.
    """

    return UserMemoryService(
        session=session,
        repository=repository,
        user_repository=user_repository,
        conversation_repository=conversation_repository,
        embedding_provider=embedding_provider,
        compliance_log=compliance_log,
    )
