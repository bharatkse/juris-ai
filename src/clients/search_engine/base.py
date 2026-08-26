"""
Base web search client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.dto.clients.search_engine import (
    SearchEngineRequestDTO,
    SearchEngineResponseDTO,
)


class SearchClient(ABC):
    """
    Base class for all web search providers.
    """

    @abstractmethod
    async def search(
        self,
        *,
        request: SearchEngineRequestDTO,
    ) -> SearchEngineResponseDTO:
        """
        Search the web.

        Args:
            request:
                Search request.

        Returns:
            Search response.
        """
        raise NotImplementedError
