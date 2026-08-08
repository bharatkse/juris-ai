"""
Base tool contract.

Defines the common interface implemented by all AI tools.

A tool performs a single, well-defined operation on behalf of an AI
agent. Tools are stateless and reusable across multiple agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.models.tool import ToolMetadata, ToolRequest, ToolResponse


class BaseTool(ABC):
    """
    Base class for all AI tools.

    Tools are singleton, stateless application services.
    """

    metadata: ToolMetadata

    @abstractmethod
    async def run(
        self,
        *,
        request: ToolRequest,
    ) -> ToolResponse:
        """
        Execute the tool.

        Args:
            request:
                Tool execution request.

        Returns:
            Tool execution response.
        """
        raise NotImplementedError
