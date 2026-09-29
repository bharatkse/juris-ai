"""
Unit tests for the API router.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from api.dependencies.auth import get_current_user
from api.v1.routers import api_router

# Routes deliberately reachable without an access token. Adding a route
# here is a security decision; every other route must authenticate.
PUBLIC_ROUTES = {
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/access-token"),  # validated with the refresh token
    ("POST", "/api/v1/users"),  # registration
}


def _requires_current_user(dependant: Dependant) -> bool:
    return any(
        dependency.call is get_current_user or _requires_current_user(dependency)
        for dependency in dependant.dependencies
    )


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

    paths = {route.path for route in iter_route_contexts(api_router.routes)}

    assert "/api/v1/health" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/conversations" in paths
    assert "/api/v1/chat" in paths


def test_api_router_registers_health_before_domain_routes() -> None:
    """
    It should register the health router before the domain routers.
    """

    paths = [route.path for route in iter_route_contexts(api_router.routes)]

    assert paths.index("/api/v1/health") < paths.index("/api/v1/users")
    assert paths.index("/api/v1/health") < paths.index("/api/v1/conversations")
    assert paths.index("/api/v1/health") < paths.index("/api/v1/chat")


def test_every_non_public_route_requires_an_authenticated_user() -> None:
    """
    Every route outside PUBLIC_ROUTES must resolve get_current_user, so a
    new route can't ship without authentication by accident.
    """

    seen = set()
    unauthenticated = []

    for context in iter_route_contexts(api_router.routes):
        route = context.route
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            key = (method, context.path)
            seen.add(key)
            if key not in PUBLIC_ROUTES and not _requires_current_user(route.dependant):
                unauthenticated.append(key)

    assert unauthenticated == []
    assert PUBLIC_ROUTES <= seen, "stale entries in PUBLIC_ROUTES"
