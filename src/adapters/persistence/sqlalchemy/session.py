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

from config.settings import get_settings

settings = get_settings()


def _create_engine() -> AsyncEngine:
    """
    Create the application's SQLAlchemy async engine.

    Returns:
        Configured SQLAlchemy AsyncEngine.
    """

    return create_async_engine(
        url=settings.async_database_url,
        echo=settings.app.DEBUG,
        pool_pre_ping=True,
        pool_size=settings.database.DATABASE_POOL_SIZE,
        max_overflow=settings.database.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.database.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.database.DATABASE_POOL_RECYCLE,
        connect_args={
            "server_settings": {
                "application_name": settings.app.APP_NAME,
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


async def dispose_engine() -> None:
    """
    Discard the shared engine's connection pool.

    The pool caches live asyncpg connections, each bound to whichever
    event loop was running when it was checked out. In production this
    never matters: the app has exactly one event loop for its whole
    lifetime. It does matter for any caller that may run this module's
    session_factory() under more than one event loop in a single
    process (e.g. a test process moving between differently
    loop-scoped test blocks) -- a connection checked out under a now-closed
    loop and handed back out under a new one raises
    "Future ... attached to a different loop". Call this right before
    (and after) a block of work known to run under a different loop
    than whatever last used session_factory(), to force fresh
    connections instead of reusing stale ones.
    """

    await engine.dispose()
