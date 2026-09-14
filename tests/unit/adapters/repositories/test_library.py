"""
Tests for library file repository.
"""

from __future__ import annotations

import pytest

from adapters.persistence.sqlalchemy.repositories.library import (
    LibraryRepository,
)
from core.enums import LibraryStatusEnum
from tests.unit.factories.conversation import ConversationFactory
from tests.unit.factories.library import LibraryFactory

pytestmark = pytest.mark.asyncio


async def test_create_library(
    library_file_repository: LibraryRepository,
) -> None:
    """
    Test creating a library file.
    """

    library = LibraryFactory.build()

    created_library = await library_file_repository.create(
        library=library,
    )

    assert created_library == library
    assert created_library.id is not None


async def test_get_library(
    library_file_repository: LibraryRepository,
) -> None:
    """
    Test retrieving a library file by identifier.
    """

    library = await library_file_repository.create(
        library=LibraryFactory.build(),
    )

    retrieved_library = await library_file_repository.get_by_id(
        library_id=library.id,
    )

    assert retrieved_library == library


async def test_get_library_not_found(
    library_file_repository: LibraryRepository,
) -> None:
    """
    Test retrieving a missing library file.
    """

    library = await library_file_repository.get_by_id(
        library_id="libf_missing",
    )

    assert library is None


async def test_list_by_conversation_returns_library(
    library_file_repository: LibraryRepository,
) -> None:
    """
    Test listing library files for a conversation.
    """

    conversation = ConversationFactory.build()

    first_library = await library_file_repository.create(
        library=LibraryFactory.build(
            conversation=conversation,
        ),
    )

    second_library = await library_file_repository.create(
        library=LibraryFactory.build(
            conversation=conversation,
        ),
    )

    library = await library_file_repository.list_by_conversation(
        conversation_id=conversation.id,
    )

    assert library == [
        first_library,
        second_library,
    ]


async def test_list_by_conversation_returns_empty_list(
    library_file_repository: LibraryRepository,
) -> None:
    """
    Test listing library files when none exist.
    """

    conversation = ConversationFactory.build()

    library = await library_file_repository.list_by_conversation(
        conversation_id=conversation.id,
    )

    assert library == []


async def test_update_library(
    library_file_repository: LibraryRepository,
) -> None:
    """
    Test updating a library file.
    """

    library = await library_file_repository.create(
        library=LibraryFactory.build(),
    )

    library.status = LibraryStatusEnum.READY

    updated_library = await library_file_repository.update(
        library=library,
    )

    assert updated_library.status == LibraryStatusEnum.READY

    retrieved_library = await library_file_repository.get_by_id(
        library_id=library.id,
    )

    assert retrieved_library is not None
    assert retrieved_library.status == LibraryStatusEnum.READY


async def test_delete_library(
    library_file_repository: LibraryRepository,
) -> None:
    """
    Test deleting a library file.
    """

    library = await library_file_repository.create(
        library=LibraryFactory.build(),
    )

    await library_file_repository.delete(
        library=library,
    )

    assert (
        await library_file_repository.get_by_id(
            library_id=library.id,
        )
        is None
    )
