"""
Web search tool.
"""

from __future__ import annotations

from src.clients.web_search.base import WebSearchClient
from src.core.dto.clients.web_search import WebSearchRequestDTO
from src.core.dto.tool import ToolMetadataDTO, ToolRequestDTO, ToolResponseDTO
from src.tools.base import BaseTool


class WebSearchTool(BaseTool):
    """
    Search public information on the internet.
    """

    metadata = ToolMetadataDTO(
        name="web_search",
        description="Search publicly available web content.",
    )

    def __init__(
        self,
        *,
        client: WebSearchClient,
    ) -> None:
        self._client = client

    async def run(
        self,
        *,
        request: ToolRequestDTO,
    ) -> ToolResponseDTO:
        """
        Execute a web search.
        """

        max_results = request.parameters.get(
            "max_results",
            5,
        )

        response = await self._client.search(
            request=WebSearchRequestDTO(
                query=request.query,
                max_results=max_results,
            ),
        )

        return ToolResponseDTO(
            content=response.results,
            metadata=response.metadata,
        )
