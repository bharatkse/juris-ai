"""
Base repository.
"""

from typing import Any, ClassVar

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """
    Base class for all repositories.
    """

    _model: ClassVar[Any]

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def flush(self) -> None:
        """
        Flush pending changes.
        """
        await self._session.flush()

    async def refresh(
        self,
        entity: Any,
    ) -> None:
        """
        Refresh an ORM entity.
        """
        await self._session.refresh(entity)

    def active(self, statement: Select) -> Select:
        """Apply the soft-delete filter."""
        return statement.where(self._model.deleted_at.is_(None))
