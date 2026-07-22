"""
Base service.

Provides shared functionality for all application services.
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseService:
    """
    Base class for all services.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def commit(self) -> None:
        """
        Commit the current transaction.
        """
        await self._session.commit()

    async def rollback(self) -> None:
        """
        Roll back the current transaction.
        """
        await self._session.rollback()
