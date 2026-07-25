"""
Unit tests for request context dependency.
"""

from __future__ import annotations

from fastapi import Request

from src.api.dependencies.context import get_request_context
from src.core.context import RequestContext


def test_get_request_context_returns_request_context() -> None:
    """
    It should return the request context stored on the request.
    """

    context = RequestContext()

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        },
    )

    request.state.context = context

    returned = get_request_context(
        request,
    )

    assert returned is context
