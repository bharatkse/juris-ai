"""
Base tool contract.

Defines the common interface implemented by all AI tools.

A tool performs a single, well-defined operation on behalf of an AI
agent. Tools are stateless and reusable across multiple agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.dto.tool import ToolMetadataDTO, ToolRequestDTO, ToolResponseDTO


class BaseTool(ABC):
    """
    Base class for all AI tools.

    Tools are singleton, stateless application services.
    """

    metadata: ToolMetadataDTO

    @abstractmethod
    async def run(
        self,
        *,
        request: ToolRequestDTO,
    ) -> ToolResponseDTO:
        """
        Execute the tool.

        Args:
            request:
                Tool execution request.

        Returns:
            Tool execution response.
        """
        raise NotImplementedError
