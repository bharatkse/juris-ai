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

from src.core.constants import TEST_DB_URL
from src.db.base import Base
from src.db.models.document_chunk import DocumentChunk


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        TEST_DB_URL,
        future=True,
    )

    test_tables = [
        table for table in Base.metadata.sorted_tables if table.name != DocumentChunk.__tablename__
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
