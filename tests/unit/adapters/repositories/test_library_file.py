"""
Tests for library file repository.
"""

from __future__ import annotations

import pytest

from adapters.persistence.sqlalchemy.repositories.library_file import (
    LibraryFileRepository,
)
from core.enums import LibraryFileStatusEnum
from tests.factories.conversation import ConversationFactory
from tests.factories.upload_file import LibraryFileFactory

pytestmark = pytest.mark.asyncio


async def test_create_library_file(
    upload_file_repository: LibraryFileRepository,
) -> None:
    """
    Test creating a library file.
    """

    library_file = LibraryFileFactory.build()

    created_library_file = await upload_file_repository.create(
        library_file=library_file,
    )

    assert created_library_file == library_file
    assert created_library_file.id is not None


async def test_get_library_file(
    upload_file_repository: LibraryFileRepository,
) -> None:
    """
    Test retrieving a library file by identifier.
    """

    library_file = await upload_file_repository.create(
        library_file=LibraryFileFactory.build(),
    )

    retrieved_library_file = await upload_file_repository.get_by_id(
        library_file_id=library_file.id,
    )

    assert retrieved_library_file == library_file


async def test_get_library_file_not_found(
    upload_file_repository: LibraryFileRepository,
) -> None:
    """
    Test retrieving a missing library file.
    """

    library_file = await upload_file_repository.get_by_id(
        library_file_id="libf_missing",
    )

    assert library_file is None


async def test_list_by_conversation_returns_library_files(
    upload_file_repository: LibraryFileRepository,
) -> None:
    """
    Test listing library files for a conversation.
    """

    conversation = ConversationFactory.build()

    first_library_file = await upload_file_repository.create(
        library_file=LibraryFileFactory.build(
            conversation=conversation,
        ),
    )

    second_library_file = await upload_file_repository.create(
        library_file=LibraryFileFactory.build(
            conversation=conversation,
        ),
    )

    library_files = await upload_file_repository.list_by_conversation(
        conversation_id=conversation.id,
    )

    assert library_files == [
        first_library_file,
        second_library_file,
    ]


async def test_list_by_conversation_returns_empty_list(
    upload_file_repository: LibraryFileRepository,
) -> None:
    """
    Test listing library files when none exist.
    """

    conversation = ConversationFactory.build()

    library_files = await upload_file_repository.list_by_conversation(
        conversation_id=conversation.id,
    )

    assert library_files == []


async def test_update_library_file(
    upload_file_repository: LibraryFileRepository,
) -> None:
    """
    Test updating a library file.
    """

    library_file = await upload_file_repository.create(
        library_file=LibraryFileFactory.build(),
    )

    library_file.status = LibraryFileStatusEnum.READY

    updated_library_file = await upload_file_repository.update(
        library_file=library_file,
    )

    assert updated_library_file.status == LibraryFileStatusEnum.READY

    retrieved_library_file = await upload_file_repository.get_by_id(
        library_file_id=library_file.id,
    )

    assert retrieved_library_file is not None
    assert retrieved_library_file.status == LibraryFileStatusEnum.READY


async def test_delete_library_file(
    upload_file_repository: LibraryFileRepository,
) -> None:
    """
    Test deleting a library file.
    """

    library_file = await upload_file_repository.create(
        library_file=LibraryFileFactory.build(),
    )

    await upload_file_repository.delete(
        library_file=library_file,
    )

    assert (
        await upload_file_repository.get_by_id(
            library_file_id=library_file.id,
        )
        is None
    )
