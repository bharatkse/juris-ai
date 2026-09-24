"""
Case law search tool.

Singleton, built once at startup — same session-factory pattern as
file_lookup.py, for the same reason (no bound session held across
requests). Unlike file_lookup.py, this tool does not read
request_context at all: see CaseLawSearchTool's docstring for why
search_contracts() is intentionally not ACL-scoped.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.knowledge_sources import KnowledgeSourceRepository
from agentic.tools.base import Tool
from agentic.tools.search_engine.web_research import WebResearchTool
from core.exceptions.domain import DomainError

log = get_logger(__name__)


class CaseLawSearchTool(Tool):
    """
    Search external case law (via WebResearchTool) and internal
    contracts (via KnowledgeSourceRepository).

    search_contracts() is deliberately NOT ACL-scoped: KnowledgeSource
    (see its own model docstring) is an intentionally unrestricted,
    shared, admin-curated corpus -- populated only by the offline
    ingestion pipeline (rag/ingestion/ingest_offline.py), never through
    a per-user upload API. It has no per-user ownership column and
    none is implied by its design; unlike Library (real per-user
    uploads, ownership via Conversation.user_id -- see
    agentic/tools/library/file_lookup.py, which IS ACL-scoped), there
    is no "owner" here to restrict access by. A previous version of
    this method referenced RequestContext.allowed_knowledge_source_ids,
    an attribute that never existed on RequestContext -- dead code that
    would have raised AttributeError the moment this scope actually
    ran, not a security control this change removes.
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

        try:
            async with self._session_factory() as session:
                repository = KnowledgeSourceRepository(session=session)
                knowledge_sources = await repository.search(query=query, limit=limit)

        except DomainError:
            log.exception("Repository error searching contracts.")
            return "Contract search failed — please try again."

        if not knowledge_sources:
            return "No matching contracts found."

        # KnowledgeSource has no `title` field either (same shape of
        # bug just fixed on the Library side, found while touching this
        # exact line -- see LibraryRepository.search()/file_lookup.py).
        return "\n".join(
            f"- {d.id}: {d.filename or d.original_filename or d.id}" for d in knowledge_sources
        )

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
