"""
Compliance log dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.session import get_db_session
from application.services.compliance_log import ComplianceLogService


def get_compliance_log_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> ComplianceLogRepository:
    """
    Create a ComplianceLogRepository.
    """

    return ComplianceLogRepository(
        session=session,
    )


def get_compliance_log_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    repository: ComplianceLogRepository = Depends(
        get_compliance_log_repository,
    ),
) -> ComplianceLogService:
    """
    Create a ComplianceLogService.
    """

    return ComplianceLogService(
        session=session,
        repository=repository,
    )
