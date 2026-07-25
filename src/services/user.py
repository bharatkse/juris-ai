"""
User service.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import UserAlreadyExistsError, UserNotFoundError
from src.core.types import UserId
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

    @staticmethod
    def _normalize_field_value(
        field_value: str,
    ) -> str:
        return field_value.strip().lower()

    async def create(
        self,
        request: CreateUserRequest,
    ) -> User:
        """
        Create a new user.
        """

        password_hash = self._password_service.hash(request.password)

        data = request.model_dump(
            exclude={
                "password",
                "confirm_password",
            }
        )

        data["email"] = self._normalize_field_value(data["email"])

        if await self._repository.exists_by_email(data["email"]):
            raise UserAlreadyExistsError("Email is already registered.")

        data["hashed_password"] = password_hash
        user = User(**data)

        try:
            user = await self._repository.create(user)
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

        return await self._repository.get(user_id)

    async def update(
        self,
        user_id: UserId,
        request: UpdateUserRequest,
    ) -> User | None:
        """
        Update a user's profile.
        """
        user = await self._repository.get(user_id)

        if user is None:
            raise UserNotFoundError("User not found.")

        updates = request.model_dump(exclude_unset=True)

        for field, value in updates.items():
            # if field == "email":
            #     value = value.strip().lower()

            #     if value != user.email:
            #         if await self._repository.exists_by_email(value):
            #             raise UserAlreadyExistsError("Email is already registered.")

            setattr(user, field, value)

        try:
            await self._repository.update(user)

            await self.commit()

            return user

        except Exception:
            await self.rollback()
            raise
