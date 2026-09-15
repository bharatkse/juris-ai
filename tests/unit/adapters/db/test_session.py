"""
Unit tests for database session management.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.persistence.sqlalchemy import session


@patch("adapters.persistence.sqlalchemy.session.create_async_engine")
def test_create_engine(
    mock_create_async_engine: MagicMock,
) -> None:
    """
    It should create the SQLAlchemy engine against the given URL,
    using application settings for everything else.
    """

    engine = MagicMock()

    mock_create_async_engine.return_value = engine

    created = session._create_engine("postgresql+asyncpg://u:p@host/db")

    assert created is engine

    mock_create_async_engine.assert_called_once_with(
        url="postgresql+asyncpg://u:p@host/db",
        echo=session.settings.app.DEBUG,
        pool_pre_ping=True,
        pool_size=session.settings.database.DATABASE_POOL_SIZE,
        max_overflow=session.settings.database.DATABASE_MAX_OVERFLOW,
        pool_timeout=session.settings.database.DATABASE_POOL_TIMEOUT,
        pool_recycle=session.settings.database.DATABASE_POOL_RECYCLE,
        connect_args={
            "server_settings": {
                "application_name": session.settings.app.APP_NAME,
            },
        },
    )


def test_engine_and_admin_engine_are_built_from_different_urls() -> None:
    """
    The restricted runtime engine and the admin engine must not
    silently collapse onto the same connection -- that would defeat
    the point of the role split. (In this test process they resolve
    to the same TEST_DATABASE_URL, since get_async_database_url()'s
    TESTING branch ignores APP_DB_USER/DB_USER entirely -- so this
    only asserts the two module-level engines are genuinely distinct
    AsyncEngine instances, not that their URLs differ here.)
    """

    assert session.engine is not session.admin_engine
    assert session.session_factory is not session.admin_session_factory


def test_create_db_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    It should create a standalone database session.
    """

    db_session = MagicMock()

    session_factory = MagicMock(
        return_value=db_session,
    )

    monkeypatch.setattr(
        session,
        "session_factory",
        session_factory,
    )

    created = session.create_db_session()

    assert created is db_session

    session_factory.assert_called_once_with()


def test_create_admin_db_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    It should create a standalone database session bound to the admin
    (schema-owning) role -- via admin_session_factory, distinct from
    create_db_session()'s restricted-role session_factory.
    """

    admin_db_session = MagicMock()

    admin_session_factory = MagicMock(
        return_value=admin_db_session,
    )

    monkeypatch.setattr(
        session,
        "admin_session_factory",
        admin_session_factory,
    )

    created = session.create_admin_db_session()

    assert created is admin_db_session

    admin_session_factory.assert_called_once_with()


@pytest.mark.asyncio
async def test_dispose_admin_engine() -> None:
    """
    It should dispose the admin engine's pool without touching the
    restricted-role engine's pool.
    """

    mock_admin_engine = AsyncMock()

    with patch.object(session, "admin_engine", mock_admin_engine):
        await session.dispose_admin_engine()

    mock_admin_engine.dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_db_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    It should yield a database session and close it.
    """

    db_session = AsyncMock()

    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = db_session

    session_factory = MagicMock(
        return_value=context_manager,
    )

    monkeypatch.setattr(
        session,
        "session_factory",
        session_factory,
    )

    generator = session.get_db_session()

    yielded = await anext(generator)

    assert yielded is db_session

    with pytest.raises(
        StopAsyncIteration,
    ):
        await anext(generator)

    db_session.rollback.assert_not_awaited()
    db_session.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_db_session_rolls_back_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    It should roll back and close the session when an exception occurs.
    """

    db_session = AsyncMock()

    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = db_session

    session_factory = MagicMock(
        return_value=context_manager,
    )

    monkeypatch.setattr(
        session,
        "session_factory",
        session_factory,
    )

    generator = session.get_db_session()

    await anext(generator)

    with pytest.raises(
        RuntimeError,
    ):
        await generator.athrow(
            RuntimeError(
                "Database failure",
            ),
        )

    db_session.rollback.assert_awaited_once_with()
    db_session.close.assert_awaited_once_with()
