"""
Authorization API dependencies.
"""

from __future__ import annotations

from src.authorization.service import AuthorizationService
from src.runtime.factories.authorization import create_authorization


def get_authorization_service() -> AuthorizationService:
    """
    Create the application authorization service.
    """

    return create_authorization()
