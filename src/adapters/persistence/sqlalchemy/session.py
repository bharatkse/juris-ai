"""
Database engine and session management.

This module is responsible for:

- Creating the SQLAlchemy async engine
- Creating the shared session factory
- Providing FastAPI request-scoped database sessions
- Providing standalone sessions for background jobs and scripts

Database schema migrations are managed separately using Alembic.

Two engines/session factories are exposed, not one:

- engine / session_factory / get_db_session() / create_db_session():
  the restricted runtime role (APP_DB_USER in DEVELOPMENT -- see
  config.database.DatabaseSettings). Everything in normal
  request-handling code paths uses these.
- admin_engine / admin_session_factory / create_admin_db_session():
  the schema-owning admin/migration role (DB_USER). Reserved for the
  small set of admin-only scripts that need privilege the restricted
  role deliberately doesn't have (see settings.admin_async_database_url's
  docstring for the concrete callers). Never use these in normal
  request-handling code -- that defeats the point of the role split.
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


def _create_engine(url: str) -> AsyncEngine:
    """
    Create a SQLAlchemy async engine against the given connection URL.

    Returns:
        Configured SQLAlchemy AsyncEngine.
    """

    return create_async_engine(
        url=url,
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
# Shared database engine -- restricted runtime role. All normal
# request handling goes through this.
#
engine: AsyncEngine = _create_engine(settings.async_database_url)


#
# Shared session factory -- restricted runtime role.
#
session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


#
# Admin engine/session factory -- schema-owning admin/migration role.
# Admin-only scripts only; see module docstring.
#
admin_engine: AsyncEngine = _create_engine(settings.admin_async_database_url)

admin_session_factory = async_sessionmaker(
    bind=admin_engine,
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
    Create a standalone database session (restricted runtime role).

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


def create_admin_db_session() -> AsyncSession:
    """
    Create a standalone database session using the admin/migration
    role -- not the restricted runtime role create_db_session() above
    returns. For the small set of admin-only scripts that need
    privilege the restricted role deliberately doesn't have; see this
    module's docstring for the concrete callers. Do not use this for
    normal request-handling code.

    Returns:
        New AsyncSession instance, bound to the admin engine.
    """

    return admin_session_factory()


async def dispose_engine() -> None:
    """
    Discard the shared (restricted-role) engine's connection pool.

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

    Does not touch admin_engine -- callers that mix admin_session_factory
    into the same cross-loop test flow must also call
    dispose_admin_engine() separately.
    """

    await engine.dispose()


async def dispose_admin_engine() -> None:
    """
    Discard the admin (schema-owning) engine's connection pool. Same
    cross-event-loop rationale as dispose_engine() above, for code
    that uses admin_session_factory/create_admin_db_session() instead
    of the restricted-role session_factory.
    """

    await admin_engine.dispose()
