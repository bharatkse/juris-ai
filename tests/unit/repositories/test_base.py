"""
Unit tests for BaseRepository.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from src.db.models.conversation import Conversation
from src.repositories.base import BaseRepository


class DummyRepository(BaseRepository):
    """
    Concrete repository used for testing.
    """

    _model = Conversation


@pytest.fixture
def repository(
    mock_async_session: AsyncMock,
) -> DummyRepository:
    """
    Create a repository backed by a mocked async session.
    """

    return DummyRepository(
        session=mock_async_session,
    )


@pytest.mark.asyncio
async def test_flush_calls_session_flush(
    repository: DummyRepository,
    mock_async_session: AsyncMock,
) -> None:
    """
    It should flush pending changes.
    """

    await repository.flush()

    mock_async_session.flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_refresh_calls_session_refresh(
    repository: DummyRepository,
    mock_async_session: AsyncMock,
) -> None:
    """
    It should refresh the ORM entity.
    """

    entity: MagicMock = MagicMock()

    await repository.refresh(
        entity,
    )

    mock_async_session.refresh.assert_awaited_once_with(
        entity,
    )


def test_active_filters_soft_deleted_entities(
    repository: DummyRepository,
) -> None:
    """
    It should exclude soft-deleted entities.
    """

    statement = select(
        Conversation,
    )

    filtered = repository.active(
        statement,
    )

    compiled = str(
        filtered.compile(
            compile_kwargs={
                "literal_binds": True,
            },
        )
    ).upper()

    assert "DELETED_AT" in compiled
    assert "IS NULL" in compiled
