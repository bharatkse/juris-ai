"""
Unit tests for database session management.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db import session


@patch("src.db.session.create_async_engine")
def test_create_engine(
    mock_create_async_engine: MagicMock,
) -> None:
    """
    It should create the SQLAlchemy engine using application settings.
    """

    engine = MagicMock()

    mock_create_async_engine.return_value = engine

    created = session._create_engine()

    assert created is engine

    mock_create_async_engine.assert_called_once_with(
        url=session.settings.async_database_url,
        echo=session.settings.DEBUG,
        pool_pre_ping=True,
        pool_size=session.settings.DATABASE_POOL_SIZE,
        max_overflow=session.settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=session.settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=session.settings.DATABASE_POOL_RECYCLE,
        connect_args={
            "server_settings": {
                "application_name": session.settings.APP_NAME,
            },
        },
    )


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
