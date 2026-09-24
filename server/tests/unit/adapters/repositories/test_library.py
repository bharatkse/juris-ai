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
from tests.unit.factories.user import UserFactory

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


# ---------------------------------------------------------------------------
# Per-user ownership enforcement -- the actual security boundary
# AuthorizationService.get_allowed_library_ids() relies on
# list_owned_ids() for, and search()/list_by_conversation() enforce
# via allowed_library_ids at the SQL level. Real rows, real users,
# real query -- not application-level post-filtering.
# ---------------------------------------------------------------------------


async def test_list_owned_ids_returns_only_the_requesting_users_own_rows(
    library_file_repository: LibraryRepository,
) -> None:
    """
    The core ownership query: user A's Library rows come back for
    user A, user B's rows never do -- even though both exist in the
    same database, queried through the same repository.
    """

    user_a = UserFactory.build()
    user_b = UserFactory.build()

    conversation_a = ConversationFactory.build(user=user_a)
    conversation_b = ConversationFactory.build(user=user_b)

    library_a1 = await library_file_repository.create(
        library=LibraryFactory.build(conversation=conversation_a),
    )
    library_a2 = await library_file_repository.create(
        library=LibraryFactory.build(conversation=conversation_a),
    )
    library_b1 = await library_file_repository.create(
        library=LibraryFactory.build(conversation=conversation_b),
    )

    owned_by_a = await library_file_repository.list_owned_ids(user_id=user_a.id)
    owned_by_b = await library_file_repository.list_owned_ids(user_id=user_b.id)

    assert owned_by_a == {library_a1.id, library_a2.id}
    assert owned_by_b == {library_b1.id}
    assert library_b1.id not in owned_by_a
    assert library_a1.id not in owned_by_b
    assert library_a2.id not in owned_by_b


async def test_list_owned_ids_returns_empty_set_for_a_user_with_no_library_rows(
    library_file_repository: LibraryRepository,
) -> None:
    user = UserFactory.build()

    owned = await library_file_repository.list_owned_ids(user_id=user.id)

    assert owned == set()


async def test_search_with_allowed_library_ids_excludes_another_users_rows(
    library_file_repository: LibraryRepository,
) -> None:
    """
    search() applies the owner filter in SQL, not as a caller-side
    post-filter: passing allowed_library_ids scoped to user A must
    never return user B's row, even when B's file would otherwise
    match the query text.
    """

    user_a = UserFactory.build()
    user_b = UserFactory.build()

    conversation_a = ConversationFactory.build(user=user_a)
    conversation_b = ConversationFactory.build(user=user_b)

    library_a = await library_file_repository.create(
        library=LibraryFactory.build(
            conversation=conversation_a,
            filename="shared_keyword_report.pdf",
        ),
    )
    await library_file_repository.create(
        library=LibraryFactory.build(
            conversation=conversation_b,
            filename="shared_keyword_report.pdf",
        ),
    )

    allowed_for_a = await library_file_repository.list_owned_ids(user_id=user_a.id)

    results = await library_file_repository.search(
        query="shared_keyword_report",
        allowed_library_ids=allowed_for_a,
    )

    assert [r.id for r in results] == [library_a.id]


async def test_search_with_empty_allowed_library_ids_returns_nothing(
    library_file_repository: LibraryRepository,
) -> None:
    """
    A user who owns nothing must get nothing back, not an unscoped
    result -- confirms the empty-set short-circuit doesn't
    accidentally behave like "no restriction" (None).
    """

    await library_file_repository.create(
        library=LibraryFactory.build(filename="anything.pdf"),
    )

    results = await library_file_repository.search(
        query="anything",
        allowed_library_ids=set(),
    )

    assert results == []


async def test_search_without_allowed_library_ids_is_unrestricted(
    library_file_repository: LibraryRepository,
) -> None:
    """
    allowed_library_ids=None (the default) preserves the previous,
    unrestricted behavior -- for callers that have already resolved
    "no restriction" deliberately, not by omission.
    """

    library = await library_file_repository.create(
        library=LibraryFactory.build(filename="unique_search_target.pdf"),
    )

    results = await library_file_repository.search(query="unique_search_target")

    assert [r.id for r in results] == [library.id]


async def test_list_by_conversation_with_allowed_library_ids_excludes_other_rows(
    library_file_repository: LibraryRepository,
) -> None:
    conversation = ConversationFactory.build()

    library_1 = await library_file_repository.create(
        library=LibraryFactory.build(conversation=conversation),
    )
    library_2 = await library_file_repository.create(
        library=LibraryFactory.build(conversation=conversation),
    )

    results = await library_file_repository.list_by_conversation(
        conversation_id=conversation.id,
        allowed_library_ids={library_1.id},
    )

    assert [r.id for r in results] == [library_1.id]
    assert library_2.id not in [r.id for r in results]
