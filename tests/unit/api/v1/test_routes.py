"""
Unit tests for the API router.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.v1.routers import api_router


def test_api_router_has_expected_prefix() -> None:
    """
    It should configure the API v1 prefix.
    """

    assert api_router.prefix == "/api/v1"


def test_api_router_is_api_router() -> None:
    """
    It should create a FastAPI APIRouter.
    """

    assert isinstance(
        api_router,
        APIRouter,
    )


def test_api_router_registers_expected_routes() -> None:
    """
    It should register all endpoint routers.
    """

    paths = {route.path for route in api_router.routes}

    assert "/api/v1/health" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/conversations" in paths
    assert "/api/v1/chat" in paths


def test_api_router_registers_health_before_domain_routes() -> None:
    """
    It should register the health router before the domain routers.
    """

    paths = [route.path for route in api_router.routes]

    assert paths.index("/api/v1/health") < paths.index("/api/v1/users")
    assert paths.index("/api/v1/health") < paths.index("/api/v1/conversations")
    assert paths.index("/api/v1/health") < paths.index("/api/v1/chat")
