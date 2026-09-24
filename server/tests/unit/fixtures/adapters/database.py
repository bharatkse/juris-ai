"""
Database test fixtures.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.models.knowledge_chunk import KnowledgeChunk
from core.constants import TEST_DB_URL


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Session-scoped test engine.

    loop_scope="session" is required now that
    asyncio_default_fixture_loop_scope is "function": a session-scoped
    fixture's own loop_scope must be at least as broad as its fixture
    scope, or pytest-asyncio rejects it outright.

    NullPool (rather than the default pooled connections) is what
    actually keeps this safe for db_session, which is function-scoped
    and therefore runs under a fresh event loop per test: a pooled
    asyncpg connection checked out under one test's loop and handed
    back to a later test's different loop raises "Future attached to a
    different loop". NullPool never hands out a connection that
    outlived its checkout, so no connection ever crosses a loop
    boundary. This is a test-only engine -- the production engine
    (adapters/persistence/sqlalchemy/session.py) keeps real pooling,
    since the app has exactly one event loop for its whole lifetime.
    """

    engine = create_async_engine(
        TEST_DB_URL,
        future=True,
        poolclass=NullPool,
    )

    test_tables = [
        table for table in Base.metadata.sorted_tables if table.name != KnowledgeChunk.__tablename__
    ]

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=test_tables,
            )
        )

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.drop_all(
                sync_conn,
                tables=test_tables,
            )
        )

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Return an async transactional database session.
    """

    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session() as session:
        yield session

        await session.rollback()


@pytest.fixture
def mock_async_session() -> AsyncMock:
    """
    Create a mocked asynchronous database session.
    """

    return AsyncMock(
        spec=AsyncSession,
    )
