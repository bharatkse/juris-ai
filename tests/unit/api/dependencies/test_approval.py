"""
Unit tests for approval API dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.approval import (
    get_approval_lifecycle_service,
    get_approval_repository,
)
from src.repositories.approval import ApprovalRepository
from src.services.approval_lifecycle import ApprovalLifecycleService


def test_get_approval_repository_returns_repository() -> None:
    """
    It should create an ApprovalRepository.
    """

    session = MagicMock(
        spec=AsyncSession,
    )

    result = get_approval_repository(
        session=session,
    )

    assert isinstance(
        result,
        ApprovalRepository,
    )


def test_get_approval_repository_uses_supplied_session() -> None:
    """
    It should pass the supplied session to the repository.
    """

    session = MagicMock(
        spec=AsyncSession,
    )

    result = get_approval_repository(
        session=session,
    )

    assert result._session is session


def test_get_approval_lifecycle_service_returns_service() -> None:
    """
    It should create an ApprovalLifecycleService.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    repository = MagicMock(
        spec=ApprovalRepository,
    )

    result = get_approval_lifecycle_service(
        session=session,
        repository=repository,
    )

    assert isinstance(
        result,
        ApprovalLifecycleService,
    )


def test_get_approval_lifecycle_service_uses_supplied_dependencies() -> None:
    """
    It should pass the supplied session and repository to the service.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    repository = MagicMock(
        spec=ApprovalRepository,
    )

    result = get_approval_lifecycle_service(
        session=session,
        repository=repository,
    )

    assert result._session is session
    assert result._repository is repository
