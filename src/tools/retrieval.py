"""
Knowledge retrieval tool.
"""

from __future__ import annotations

import asyncio

from core.models.tool import ToolMetadata, ToolRequest, ToolResponse
from src.tools.base import BaseTool
from src.tools.parser import ParserTool
from src.tools.web_search import WebSearchTool


class RetrieverTool(BaseTool):
    """
    Retrieve relevant knowledge for the current request.

    The retriever combines uploaded document parsing and
    external web search into a unified retrieval result.
    """

    metadata = ToolMetadata(
        name="retriever",
        description=(
            "Retrieve relevant information from uploaded "
            "documents and external knowledge sources."
        ),
    )

    def __init__(
        self,
        *,
        parser_tool: ParserTool,
        web_search_tool: WebSearchTool,
    ) -> None:
        self._parser = parser_tool
        self._web_search = web_search_tool

    async def run(
        self,
        *,
        request: ToolRequest,
    ) -> ToolResponse:
        """
        Retrieve relevant information.
        """

        document_response, web_response = await asyncio.gather(
            self._retrieve_documents(
                request=request,
            ),
            self._retrieve_web(
                request=request,
            ),
        )

        return ToolResponse(
            content=(
                *document_response.content,
                *web_response.content,
            ),
            metadata={
                **document_response.metadata,
                **web_response.metadata,
            },
        )

    async def _retrieve_documents(
        self,
        *,
        request: ToolRequest,
    ) -> ToolResponse:
        """
        Retrieve information from uploaded documents.
        """

        if not request.uploaded_files:
            return ToolResponse()

        return await self._parser.run(
            request=request,
        )

    async def _retrieve_web(
        self,
        *,
        request: ToolRequest,
    ) -> ToolResponse:
        """
        Retrieve information from the public web.
        """

        if not request.parameters.get(
            "web_search",
            True,
        ):
            return ToolResponse()

        return await self._web_search.run(
            request=request,
        )
