"""
Rate limit / usage quota dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.user import User
from adapters.persistence.sqlalchemy.repositories.usage_record import (
    UsageRecordRepository,
)
from adapters.persistence.sqlalchemy.session import get_db_session
from api.dependencies.auth import get_current_user
from application.services.usage import UsageService


def get_usage_record_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> UsageRecordRepository:
    """
    Create a UsageRecordRepository.
    """

    return UsageRecordRepository(
        session=session,
    )


def get_usage_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    repository: UsageRecordRepository = Depends(
        get_usage_record_repository,
    ),
) -> UsageService:
    """
    Create a UsageService.
    """

    return UsageService(
        session=session,
        repository=repository,
    )


async def enforce_usage_limits(
    current_user: User = Depends(
        get_current_user,
    ),
    usage_service: UsageService = Depends(
        get_usage_service,
    ),
) -> None:
    """
    Enforce the per-user request-rate limit and daily token quota
    before dispatching to the orchestrator.

    Depends on get_current_user, so this must be listed after
    current_user in an endpoint's dependency list -- there is no user
    to rate-limit before authentication resolves one. Raises
    RateLimitExceededError / TokenQuotaExceededError (both mapped to
    HTTP 429 by the global exception handlers) when a limit is
    exceeded.
    """

    await usage_service.check_and_enforce(
        user_id=current_user.id,
    )
