"""
Database engine and session management.

This module is responsible for:

- Creating the SQLAlchemy async engine
- Creating the shared session factory
- Providing FastAPI request-scoped database sessions
- Providing standalone sessions for background jobs and scripts

Database schema migrations are managed separately using Alembic.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings


def _create_engine() -> AsyncEngine:
    """
    Create the application's SQLAlchemy async engine.

    Returns:
        Configured SQLAlchemy AsyncEngine.
    """

    return create_async_engine(
        url=settings.database_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        connect_args={
            "server_settings": {
                "application_name": settings.APP_NAME,
            },
        },
    )


#
# Shared database engine
#
engine: AsyncEngine = _create_engine()


#
# Shared session factory
#
session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a request-scoped database session.

    Transaction handling:

    - Commit if the request completes successfully.
    - Rollback if any exception occurs.
    - Always close the session.
    """

    async with session_factory() as session:
        try:
            yield session

        except BaseException:
            await session.rollback()
            raise

        finally:
            await session.close()


def create_db_session() -> AsyncSession:
    """
    Create a standalone database session.

    Intended for:

    - Background jobs
    - LangGraph workflows
    - CLI commands
    - Scheduled tasks
    - Data migration scripts

    Returns:
        New AsyncSession instance.
    """

    return session_factory()
