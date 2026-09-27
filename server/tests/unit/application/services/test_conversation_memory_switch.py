"""
Unit tests for ConversationService.set_memory_disabled -- the
per-conversation "don't remember this" switch (forward-only).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from application.services.conversation import ConversationService
from core.exceptions.database import DatabaseError
from core.exceptions.httpx import ConversationInactiveError
from core.exceptions.httpx import NotFoundError as ConversationNotFoundError


def _conversation(*, disabled: bool = False, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id="conv_1",
        user_id="user_a",
        memory_disabled=disabled,
        is_active=active,
    )


@pytest.fixture
def repository() -> MagicMock:
    mock = MagicMock()
    mock.get = AsyncMock(return_value=_conversation())
    mock.update = AsyncMock(side_effect=lambda conversation: conversation)
    return mock


@pytest.fixture
def session() -> MagicMock:
    mock = MagicMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    return mock


@pytest.fixture
def service(session: MagicMock, repository: MagicMock) -> ConversationService:
    return ConversationService(session=session, repository=repository)


async def test_turning_the_switch_on_sets_the_flag_and_commits(
    service: ConversationService,
    session: MagicMock,
) -> None:
    result = await service.set_memory_disabled(
        conversation_id="conv_1",
        user_id="user_a",
        disabled=True,
    )

    assert result.memory_disabled is True
    session.commit.assert_awaited_once()


async def test_it_is_forward_only_and_never_touches_stored_memories(
    service: ConversationService,
    repository: MagicMock,
) -> None:
    # The service has no memory repository at all: it cannot delete
    # already-extracted facts, by construction. Only the conversation row
    # is read and written.
    await service.set_memory_disabled(
        conversation_id="conv_1",
        user_id="user_a",
        disabled=True,
    )

    assert not hasattr(service, "_user_memory_repository")
    repository.update.assert_awaited_once()


async def test_setting_the_current_value_is_a_noop(
    service: ConversationService,
    repository: MagicMock,
    session: MagicMock,
) -> None:
    repository.get.return_value = _conversation(disabled=True)

    await service.set_memory_disabled(
        conversation_id="conv_1",
        user_id="user_a",
        disabled=True,
    )

    repository.update.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_switch_is_scoped_to_the_callers_conversation(
    service: ConversationService,
    repository: MagicMock,
) -> None:
    repository.get.return_value = None

    with pytest.raises(ConversationNotFoundError):
        await service.set_memory_disabled(
            conversation_id="conv_other",
            user_id="user_a",
            disabled=True,
        )

    repository.get.assert_awaited_once_with(conversation_id="conv_other", user_id="user_a")


async def test_an_archived_conversation_cannot_be_switched(
    service: ConversationService,
    repository: MagicMock,
) -> None:
    repository.get.return_value = _conversation(active=False)

    with pytest.raises(ConversationInactiveError):
        await service.set_memory_disabled(
            conversation_id="conv_1",
            user_id="user_a",
            disabled=True,
        )


async def test_a_database_error_rolls_back_and_is_surfaced(
    service: ConversationService,
    repository: MagicMock,
    session: MagicMock,
) -> None:
    repository.update.side_effect = SQLAlchemyError("boom")

    with pytest.raises(DatabaseError):
        await service.set_memory_disabled(
            conversation_id="conv_1",
            user_id="user_a",
            disabled=True,
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
