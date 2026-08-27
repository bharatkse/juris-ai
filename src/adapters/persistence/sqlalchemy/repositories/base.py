"""
Base repository.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(
    Generic[ModelT],
):
    """
    Base class for all repositories.
    """

    _model: type[ModelT]

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def persist(
        self,
        entity: ModelT,
    ) -> ModelT:
        """
        Persist an entity.
        """

        self._session.add(
            entity,
        )

        await self.flush()
        await self.refresh(
            entity,
        )

        return entity

    async def flush(
        self,
    ) -> None:
        """
        Flush pending changes.
        """

        await self._session.flush()

    async def refresh(
        self,
        entity: ModelT,
    ) -> None:
        """
        Refresh an entity.
        """

        await self._session.refresh(
            entity,
        )

    def active(
        self,
        statement: Select,
    ) -> Select:
        """
        Apply the soft-delete filter.
        """

        return statement.where(
            self._model.deleted_at.is_(None),
        )

    def select(
        self,
    ) -> Select:
        """
        Create a select statement for the repository model.
        """

        return select(
            self._model,
        )

    def active_select(
        self,
    ) -> Select:
        """
        Create a select statement filtered to active entities.
        """

        return self.active(
            self.select(),
        )
