"""
User repository.
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import exists, select

from src.core.types import UserId
from src.db.models.user import User
from src.repositories.base import BaseRepository


class UserRepository(
    BaseRepository[User],
):
    """
    Repository responsible for User persistence.
    """

    _model = User

    async def create(
        self,
        user: User,
    ) -> User:
        """
        Persist a new user.
        """

        return await self.persist(
            user,
        )

    async def get(
        self,
        user_id: UserId,
    ) -> User | None:
        """
        Retrieve a user by identifier.
        """

        statement = select(
            self._model,
        ).where(
            self._model.id == user_id,
        )

        result = await self._session.execute(
            statement,
        )

        return cast(
            User | None,
            result.scalar_one_or_none(),
        )

    async def get_by_email(
        self,
        email: str,
    ) -> User | None:
        """
        Retrieve a user by email address.
        """

        statement = select(
            self._model,
        ).where(
            self._model.email == email,
        )

        result = await self._session.execute(
            statement,
        )

        return cast(
            User | None,
            result.scalar_one_or_none(),
        )

    async def exists_by_email(
        self,
        email: str,
    ) -> bool:
        """
        Check whether an email address already exists.
        """

        statement = select(
            exists().where(
                self._model.email == email,
            ),
        )

        return bool(
            await self._session.scalar(
                statement,
            ),
        )

    async def update(
        self,
        user: User,
    ) -> User:
        """
        Persist updates to a user.
        """

        await self.flush()

        await self.refresh(
            user,
        )

        return user
