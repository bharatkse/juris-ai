"""
Base service.

Provides shared functionality for all application services.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    """
    Base class for all application services.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    @property
    def session(
        self,
    ) -> AsyncSession:
        """
        Return the active database session.
        """

        return self._session

    async def flush(
        self,
    ) -> None:
        """
        Flush pending changes to the database.
        """

        await self._session.flush()

    async def refresh(
        self,
        instance: Any,
    ) -> None:
        """
        Refresh an entity from the database.
        """

        await self._session.refresh(
            instance,
        )

    async def commit(
        self,
    ) -> None:
        """
        Commit the current transaction.
        """

        await self._session.commit()

    async def rollback(
        self,
    ) -> None:
        """
        Roll back the current transaction.
        """

        await self._session.rollback()
