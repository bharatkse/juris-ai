"""
User service dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.user import UserRepository
from adapters.persistence.sqlalchemy.session import get_db_session
from adapters.security.password import PasswordService
from application.services.user import UserService


def get_password_service() -> PasswordService:
    """
    Create a password service.
    """

    return PasswordService()


def get_user_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> UserRepository:
    """
    Create a UserRepository.
    """

    return UserRepository(
        session=session,
    )


def get_user_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    repository: UserRepository = Depends(
        get_user_repository,
    ),
    password_service: PasswordService = Depends(
        get_password_service,
    ),
) -> UserService:
    """
    Create a UserService.
    """

    return UserService(
        session=session,
        repository=repository,
        password_service=password_service,
    )
