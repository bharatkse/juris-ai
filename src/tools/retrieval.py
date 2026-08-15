"""
Knowledge retrieval tool.
"""

from __future__ import annotations

import asyncio

from src.core.dto.tool import ToolMetadataDTO, ToolRequestDTO, ToolResponseDTO
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.tools.parser import ParserTool
from src.tools.web_search import WebSearchTool

logger = get_logger(__name__)


class RetrieverTool(BaseTool):
    """
    Retrieve relevant knowledge for the current request.

    The retriever combines multiple independent knowledge sources.
    Failure of one source must not prevent other sources from
    returning results.
    """

    metadata = ToolMetadataDTO(
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
        request: ToolRequestDTO,
    ) -> ToolResponseDTO:
        """
        Retrieve relevant information from all available sources.

        Individual source failures are isolated so that a failure
        in one source does not prevent other sources from returning
        useful information.
        """

        document_result, web_result = await asyncio.gather(
            self._retrieve_documents(
                request=request,
            ),
            self._retrieve_web(
                request=request,
            ),
            return_exceptions=True,
        )

        responses: list[ToolResponseDTO] = []

        if isinstance(
            document_result,
            ToolResponseDTO,
        ):
            responses.append(document_result)
        else:
            logger.warning(
                "Document retrieval failed.",
                extra={
                    "operation": "retrieve_documents",
                    "error": str(document_result),
                },
            )

        if isinstance(
            web_result,
            ToolResponseDTO,
        ):
            responses.append(web_result)
        else:
            logger.warning(
                "Web retrieval failed.",
                extra={
                    "operation": "retrieve_web",
                    "error": str(web_result),
                },
            )

        return self._merge_responses(
            responses=responses,
        )

    @staticmethod
    def _merge_responses(
        *,
        responses: list[ToolResponseDTO],
    ) -> ToolResponseDTO:
        """
        Merge successful source responses.
        """

        content: list[str] = []
        metadata: dict = {}

        for response in responses:
            content.extend(
                response.content,
            )
            metadata.update(
                response.metadata,
            )

        return ToolResponseDTO(
            content=tuple(content),
            metadata=metadata,
        )

    async def _retrieve_documents(
        self,
        *,
        request: ToolRequestDTO,
    ) -> ToolResponseDTO:
        """
        Retrieve information from uploaded documents.
        """

        if not request.uploaded_files:
            return ToolResponseDTO()

        return await self._parser.run(
            request=request,
        )

    async def _retrieve_web(
        self,
        *,
        request: ToolRequestDTO,
    ) -> ToolResponseDTO:
        """
        Retrieve information from the public web.
        """

        if not request.parameters.get(
            "web_search",
            True,
        ):
            return ToolResponseDTO()

        return await self._web_search.run(
            request=request,
        )
