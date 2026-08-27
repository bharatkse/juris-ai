"""
Unit tests for application entry point.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import main
from api.middleware.request_context import RequestContextMiddleware


@patch("main.register_exception_handlers")
def test_create_app(
    mock_register_exception_handlers: MagicMock,
) -> None:
    """
    It should create and configure the FastAPI application.
    """

    app = main.create_app()

    assert isinstance(
        app,
        FastAPI,
    )

    assert app.title == main.API_TITLE
    assert app.description == main.API_DESCRIPTION
    assert app.version == main.settings.app.APP_VERSION

    mock_register_exception_handlers.assert_called_once_with(
        app,
    )


def test_create_app_registers_api_router() -> None:
    """
    It should include the API router.
    """

    app = main.create_app()

    paths = {route.path for route in app.routes}

    assert "/" in paths
    assert "/api/v1/health" in paths


def test_create_app_registers_cors_middleware() -> None:
    """
    It should register the CORS middleware.
    """

    app = main.create_app()

    middleware = {item.cls for item in app.user_middleware}

    assert CORSMiddleware in middleware


def test_create_app_registers_request_context_middleware() -> None:
    """
    It should register the request context middleware.
    """

    app = main.create_app()

    middleware = {item.cls for item in app.user_middleware}

    assert RequestContextMiddleware in middleware


@pytest.mark.asyncio
async def test_root_endpoint() -> None:
    """
    It should expose the root endpoint.
    """

    app = main.create_app()

    root = next(route.endpoint for route in app.routes if route.path == "/")

    response = await root()

    assert isinstance(
        response,
        main.ApiResponse,
    )

    assert response.status_code == 200

    # Handle body parsing whether bytes or string
    body_data = response.body.decode() if isinstance(response.body, bytes) else response.body
    payload = json.loads(body_data)

    assert payload["success"] is True

    assert payload["data"] == {
        "name": main.settings.app.APP_NAME,
        "version": main.settings.app.APP_VERSION,
        "environment": (
            main.settings.app.ENVIRONMENT.value
            if hasattr(main.settings.app.ENVIRONMENT, "value")
            else main.settings.app.ENVIRONMENT
        ),
        "docs": ("/docs" if main.settings.app.ENABLE_DOCS else None),
        "health": "/api/v1/health",
    }


@pytest.mark.asyncio
@patch("main.create_ai_orchestrator")
@patch("main.AsyncPostgresSaver.from_conn_string")
@patch("main.logger")
@patch("main.ensure_dir")
@patch("main.setup_logging")
async def test_lifespan(
    mock_setup_logging: MagicMock,
    mock_ensure_dir: MagicMock,
    mock_log: MagicMock,
    mock_from_conn_string: MagicMock,
    mock_create_ai_orchestrator: MagicMock,
) -> None:
    """
    It should perform startup and shutdown tasks.
    """

    checkpointer = AsyncMock()

    @asynccontextmanager
    async def mock_checkpointer_context(
        connection_string: str,
    ):
        yield checkpointer

    mock_from_conn_string.side_effect = mock_checkpointer_context

    app = FastAPI()

    async with main.lifespan(app):
        pass

    mock_setup_logging.assert_called_once_with(
        level=main.settings.logging.LOG_LEVEL,
        fmt=main.settings.logging.LOG_FORMAT,
        log_file=main.settings.logging.LOG_FILE,
        max_mb=main.settings.logging.LOG_MAX_MB,
        backup_count=main.settings.logging.LOG_BACKUP_COUNT,
    )

    assert mock_ensure_dir.call_count == 2

    mock_ensure_dir.assert_any_call(
        main.settings.logging.DATA_DIRECTORY,
    )

    mock_ensure_dir.assert_any_call(
        main.settings.logging.LOG_DIRECTORY,
    )

    checkpointer.setup.assert_awaited_once_with()

    mock_create_ai_orchestrator.assert_called_once_with(
        checkpointer=checkpointer,
    )

    assert app.state.ai_orchestrator is mock_create_ai_orchestrator.return_value

    assert mock_log.info.call_count == 4

    mock_from_conn_string.assert_called_once_with(
        main.settings.langgraph_database_url,
    )


@pytest.mark.asyncio
@patch("main.ensure_dir")
@patch("main.setup_logging")
async def test_lifespan_propagates_startup_errors(
    mock_setup_logging: MagicMock,
    mock_ensure_dir: MagicMock,
) -> None:
    """
    It should propagate startup failures.
    """

    mock_ensure_dir.side_effect = RuntimeError(
        "Startup failed",
    )

    app = FastAPI()

    with pytest.raises(
        RuntimeError,
        match="Startup failed",
    ):
        async with main.lifespan(
            app,
        ):
            pass

    mock_setup_logging.assert_called_once()
