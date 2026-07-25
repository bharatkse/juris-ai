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

from src.db.base import Base


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create the async database engine.
    """

    engine = create_async_engine(
        "sqlite+aiosqlite:///./pytests.db",
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

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
