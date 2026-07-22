"""
User service.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import UserAlreadyExistsError, UserNotFoundError
from src.db.models.user import User
from src.repositories.user import UserRepository
from src.schemas.user import CreateUserRequest, UpdateUserRequest
from src.security.password import PasswordService
from src.services.base import BaseService


class UserService(BaseService):
    """
    Business logic for user management.
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        super().__init__(session)

        self._repository = repository
        self._password_service = password_service

    async def create(
        self,
        request: CreateUserRequest,
    ) -> User:
        """
        Create a new user.
        """

        email = request.email.strip().lower()

        if await self._repository.exists_by_email(email):
            raise UserAlreadyExistsError("Email is already registered.")

        password_hash = self._password_service.hash(
            request.password,
        )

        try:
            user = await self._repository.create(
                email=email,
                full_name=request.full_name.strip(),
                password_hash=password_hash,
            )

            await self.commit()

            return user

        except BaseException:
            await self.rollback()
            raise

    async def get(
        self,
        user_id: UUID,
    ) -> User | None:
        """
        Retrieve a user by identifier.
        """

        return await self._repository.get(user_id)

    async def update(
        self,
        user_id: UUID,
        request: UpdateUserRequest,
    ) -> User | None:
        """
        Update a user's profile.
        """

        user = await self._repository.get(user_id)

        if user is None:
            raise UserNotFoundError("User not found.")

        if request.full_name is not None:
            user.full_name = request.full_name.strip()

        if request.email is not None:
            email = request.email.strip().lower()

            if email != user.email:
                if await self._repository.exists_by_email(email):
                    raise UserAlreadyExistsError("Email is already registered.")

                user.email = email

        try:
            await self._repository.update(user)

            await self.commit()

            return user

        except BaseException:
            await self.rollback()
            raise
