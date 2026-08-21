"""
Aggregates all v1 routers and mounts them under a single APIRouter.
main.py imports only `api_router` from here.

Route summary
-------------

"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.v1.endpoints import approval, chat, conversations, health, users

api_router = APIRouter(prefix="/api/v1")

# Order matters for OpenAPI grouping — health first, then domain routes
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(approval.router)
