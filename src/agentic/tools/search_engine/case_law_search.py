"""
Case law search tool.

Singleton, built once at startup — same session_factory/request_context
pattern as document_lookup.py, for the same reason (no bound session
or ACL held across requests).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.knowledge_sources import KnowledgeSourceRepository
from agentic.tools.base import Tool
from agentic.tools.search_engine.web_research import WebResearchTool
from application.context.request import get_request_context
from core.exceptions.domain import DomainError

log = get_logger(__name__)


class CaseLawSearchTool(Tool):
    """
    Search external case law (via WebResearchTool) and internal
    contracts (via KnowledgeSourceRepository, ACL-scoped).
    """

    name = "case_law_search"
    description = (
        "Search for relevant case law and legal precedent on the web, "
        "or search contracts already stored in Juris-AI by content."
    )

    def __init__(
        self,
        *,
        web_research_tool: WebResearchTool,
        session_factory: async_sessionmaker,
    ) -> None:
        self._web_research_tool = web_research_tool
        self._session_factory = session_factory

    async def search_case_law(self, *, query: str, limit: int = 5) -> str:
        log.debug(
            "CaseLawSearchTool.search_case_law(limit=%d, query_length=%d).", limit, len(query)
        )

        return await self._web_research_tool.execute(
            query=f"case law {query}",
            limit=limit,
        )

    async def search_contracts(self, *, query: str, limit: int = 5) -> str:
        log.debug(
            "CaseLawSearchTool.search_contracts(limit=%d, query_length=%d).", limit, len(query)
        )

        allowed_knowledge_source_ids = get_request_context().allowed_knowledge_source_ids

        try:
            fetch_limit = limit * 3 if allowed_knowledge_source_ids is not None else limit

            async with self._session_factory() as session:
                repository = KnowledgeSourceRepository(session=session)
                knowledge_sources = await repository.search(query=query, limit=fetch_limit)

        except DomainError:
            log.exception("Repository error searching contracts.")
            return "Contract search failed — please try again."

        allowed = [
            d
            for d in knowledge_sources
            if allowed_knowledge_source_ids is None or d.id in allowed_knowledge_source_ids
        ][:limit]

        if not allowed:
            return "No matching contracts found."

        return "\n".join(f"- {d.id}: {d.title}" for d in allowed)

    async def execute(
        self,
        *,
        query: str,
        scope: str = "case_law",
        limit: int = 5,
    ) -> str:
        """
        Unified entry point matching the Tool interface.

        scope: "case_law" (default, external web via WebResearchTool)
        or "contracts" (internal full-text search).
        """

        if scope == "contracts":
            return await self.search_contracts(query=query, limit=limit)

        return await self.search_case_law(query=query, limit=limit)
