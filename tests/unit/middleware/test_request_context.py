"""
Unit tests for RequestContextMiddleware.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from src.middleware.request_context import RequestContextMiddleware


@pytest.mark.asyncio
async def test_dispatch_creates_request_context() -> None:
    """
    It should attach a request context to the request.
    """

    middleware = RequestContextMiddleware(
        app=AsyncMock(),
    )

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        },
    )

    async def call_next(
        request: Request,
    ) -> Response:
        assert hasattr(
            request.state,
            "context",
        )

        assert request.state.context.request_id

        return Response()

    await middleware.dispatch(
        request,
        call_next,
    )


@pytest.mark.asyncio
async def test_dispatch_sets_request_id_header() -> None:
    """
    It should add the request identifier to the response headers.
    """

    middleware = RequestContextMiddleware(
        app=AsyncMock(),
    )

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        },
    )

    async def call_next(
        request: Request,
    ) -> Response:
        return Response()

    response = await middleware.dispatch(
        request,
        call_next,
    )

    assert response.headers["X-Request-ID"] == request.state.context.request_id


@pytest.mark.asyncio
async def test_dispatch_calls_next_once() -> None:
    """
    It should invoke the next middleware exactly once.
    """

    middleware = RequestContextMiddleware(
        app=AsyncMock(),
    )

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        },
    )

    response = Response()

    call_next = AsyncMock(
        return_value=response,
    )

    result = await middleware.dispatch(
        request,
        call_next,
    )

    assert result is response

    call_next.assert_awaited_once_with(
        request,
    )


@pytest.mark.asyncio
async def test_dispatch_propagates_exception() -> None:
    """
    It should propagate exceptions raised by downstream middleware.
    """

    middleware = RequestContextMiddleware(
        app=AsyncMock(),
    )

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        },
    )

    async def call_next(
        request: Request,
    ) -> Response:
        raise RuntimeError(
            "Unexpected error",
        )

    with pytest.raises(
        RuntimeError,
        match="Unexpected error",
    ):
        await middleware.dispatch(
            request,
            call_next,
        )

    assert hasattr(
        request.state,
        "context",
    )
