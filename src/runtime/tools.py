"""
Runtime tool composition.

Creates and registers all AI tools.

Responsibilities:

- Create tool instances
- Register tools

No business logic belongs in this module.
"""

from __future__ import annotations

from src.runtime.containers import ClientContainer, RegistryContainer
from src.tools.parser import ParserTool
from src.tools.retrieval import RetrieverTool
from src.tools.web_search import WebSearchTool


def register_tools(
    *,
    clients: ClientContainer,
    registries: RegistryContainer,
) -> None:
    """
    Create and register all runtime tools.
    """

    parser_tool = ParserTool()

    web_search_tool = WebSearchTool(
        client=clients.web_search_client,
    )

    retriever_tool = RetrieverTool(
        parser_tool=parser_tool,
        web_search_tool=web_search_tool,
    )

    registries.tool_registry.register(
        component=parser_tool,
    )

    registries.tool_registry.register(
        component=web_search_tool,
    )

    registries.tool_registry.register(
        component=retriever_tool,
    )
