"""
Unit tests for BaseService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from application.services.base import BaseService


class DummyService(BaseService):
    """
    Concrete service used for testing.
    """


@pytest.fixture
def service(
    mock_async_session: AsyncMock,
) -> DummyService:
    """
    Create a service backed by a mocked async session.
    """

    return DummyService(
        session=mock_async_session,
    )


@pytest.mark.asyncio
async def test_commit_calls_session_commit(
    service: DummyService,
    mock_async_session: AsyncMock,
) -> None:
    """
    It should commit the current transaction.
    """

    await service.commit()

    mock_async_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_rollback_calls_session_rollback(
    service: DummyService,
    mock_async_session: AsyncMock,
) -> None:
    """
    It should roll back the current transaction.
    """

    await service.rollback()

    mock_async_session.rollback.assert_awaited_once_with()
