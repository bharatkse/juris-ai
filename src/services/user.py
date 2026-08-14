"""
User service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.httpx import UserAlreadyExistsError, UserNotFoundError
from src.db.models.user import User
from src.repositories.user import UserRepository
from src.security.password import PasswordService
from src.services.base import BaseService

if TYPE_CHECKING:
    from src.api.schemas.user import CreateUserRequest, UpdateUserRequest
    from src.core.types import UserId
    from src.repositories.user import UserRepository
    from src.security.password import PasswordService


class UserService(BaseService):
    """
    Business logic for user management.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        super().__init__(
            session=session,
        )

        self._repository = repository
        self._password_service = password_service

    @staticmethod
    def _normalize_email(
        email: str,
    ) -> str:
        """
        Normalize an email address.
        """

        return email.strip().lower()

    async def create(
        self,
        request: CreateUserRequest,
    ) -> User:
        """
        Create a new user.
        """

        data = request.model_dump(
            exclude={
                "password",
                "confirm_password",
            },
        )

        data["email"] = self._normalize_email(
            data["email"],
        )

        if await self._repository.exists_by_email(
            data["email"],
        ):
            raise UserAlreadyExistsError(
                "Email is already registered.",
            )

        user = User(
            **data,
            hashed_password=self._password_service.hash(
                request.password,
            ),
        )

        try:
            user = await self._repository.create(
                user,
            )

            await self.commit()

            return user

        except Exception:
            await self.rollback()
            raise

    async def get(
        self,
        user_id: UserId,
    ) -> User | None:
        """
        Retrieve a user by identifier.
        """

        return await self._repository.get(
            user_id,
        )

    async def get_or_raise(
        self,
        user_id: UserId,
    ) -> User:
        """
        Retrieve a user.

        Raises:
            UserNotFoundError:
                If the user does not exist.
        """

        user = await self.get(
            user_id,
        )

        if user is None:
            raise UserNotFoundError(
                "User not found.",
            )

        return user

    async def update(
        self,
        user_id: UserId,
        request: UpdateUserRequest,
    ) -> User:
        """
        Update a user's profile.
        """

        user = await self.get_or_raise(
            user_id,
        )

        updates = request.model_dump(
            exclude_unset=True,
        )

        if "email" in updates:
            email = self._normalize_email(
                updates["email"],
            )

            if email != user.email and await self._repository.exists_by_email(
                email,
            ):
                raise UserAlreadyExistsError(
                    "Email is already registered.",
                )

            updates["email"] = email

        for field, value in updates.items():
            setattr(
                user,
                field,
                value,
            )

        try:
            user = await self._repository.update(
                user,
            )

            await self.commit()

            return user

        except Exception:
            await self.rollback()
            raise
