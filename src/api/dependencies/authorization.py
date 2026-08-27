"""
Authorization API dependencies.
"""

from __future__ import annotations

from agentic.runtime.factories.authorization import create_authorization
from application.authorization.service import AuthorizationService


def get_authorization_service() -> AuthorizationService:
    """
    Create the application authorization service.
    """

    return create_authorization()
