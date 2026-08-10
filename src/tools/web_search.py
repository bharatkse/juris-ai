"""
Web search tool.
"""

from __future__ import annotations

from core.models.tool import ToolMetadata, ToolRequest, ToolResponse
from src.clients.web_search.base import WebSearchClient
from src.clients.web_search.models import WebSearchRequest
from src.tools.base import BaseTool


class WebSearchTool(BaseTool):
    """
    Search public information on the internet.
    """

    metadata = ToolMetadata(
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
        request: ToolRequest,
    ) -> ToolResponse:
        """
        Execute a web search.
        """

        max_results = request.parameters.get(
            "max_results",
            5,
        )

        response = await self._client.search(
            request=WebSearchRequest(
                query=request.query,
                max_results=max_results,
            ),
        )

        return ToolResponse(
            content=response.results,
            metadata=response.metadata,
        )
