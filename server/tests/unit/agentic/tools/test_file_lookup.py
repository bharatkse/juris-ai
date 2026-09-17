"""
Unit tests for LibraryLookupTool.

Uses the real test database (db_session) and real LibraryRepository --
not a mock -- specifically because the bugs this file fixes
(LibraryRepository.search() referencing a nonexistent Library.source_url
column; this tool returning nonexistent library.title/library.content)
would not have been caught by a repository mock that just returns
whatever attributes a test tells it to.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.library import LibraryRepository
from agentic.tools.library.file_lookup import LibraryLookupTool
from application.context.request import bind_request_context
from tests.unit.factories.conversation import ConversationFactory
from tests.unit.factories.library import LibraryFactory
from tests.unit.factories.user import UserFactory

pytestmark = pytest.mark.asyncio


class _ReuseSessionFactory:
    """
    Adapts an already-open db_session into the async_sessionmaker-shaped
    callable LibraryLookupTool expects (`async with session_factory() as
    session`), without closing or committing the shared test session --
    that stays db_session's own responsibility (rollback after the test).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _ReuseSessionFactory:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


async def test_get_library_returns_real_metadata_fields(db_session: AsyncSession) -> None:
    """
    Regression test for the get_library() field-reference bug: it used
    to build its response from library.title/library.content, neither
    of which exists on the Library model -- AttributeError the moment
    this ran against a real row.
    """

    repository = LibraryRepository(session=db_session)
    library = await repository.create(
        library=LibraryFactory.build(filename="contract_v2.pdf"),
    )

    tool = LibraryLookupTool(session_factory=_ReuseSessionFactory(db_session))

    with bind_request_context() as context:
        context.allowed_library_ids = None

        output = await tool.get_library(library_id=library.id)

    assert "contract_v2.pdf" in output
    assert str(library.status) in output or library.status.value in output
    assert library.mime_type in output


async def test_get_library_denies_a_library_id_outside_the_allowed_set(
    db_session: AsyncSession,
) -> None:
    repository = LibraryRepository(session=db_session)
    library = await repository.create(
        library=LibraryFactory.build(filename="someone_elses_file.pdf"),
    )

    tool = LibraryLookupTool(session_factory=_ReuseSessionFactory(db_session))

    with bind_request_context() as context:
        context.allowed_library_ids = {"liby_not_this_one"}

        output = await tool.get_library(library_id=library.id)

    assert "No upload file found" in output
    assert "someone_elses_file.pdf" not in output


async def test_list_library_only_returns_the_callers_allowed_rows(
    db_session: AsyncSession,
) -> None:
    """
    End-to-end through the tool: the SQL-level filter
    (LibraryRepository.search()'s allowed_library_ids) is what actually
    keeps another user's file out of the results here, not just the
    tool's own post-filter comprehension.
    """

    repository = LibraryRepository(session=db_session)

    user_a = UserFactory.build()
    user_b = UserFactory.build()
    conversation_a = ConversationFactory.build(user=user_a)
    conversation_b = ConversationFactory.build(user=user_b)

    library_a = await repository.create(
        library=LibraryFactory.build(
            conversation=conversation_a,
            filename="acl_shared_term.pdf",
        ),
    )
    await repository.create(
        library=LibraryFactory.build(
            conversation=conversation_b,
            filename="acl_shared_term.pdf",
        ),
    )

    allowed_for_a = await repository.list_owned_ids(user_id=user_a.id)

    tool = LibraryLookupTool(session_factory=_ReuseSessionFactory(db_session))

    with bind_request_context() as context:
        context.allowed_library_ids = allowed_for_a

        output = await tool.list_library(query="acl_shared_term")

    assert library_a.id in output
    assert output.count("acl_shared_term.pdf") == 1
