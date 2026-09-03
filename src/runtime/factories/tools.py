"""
Runtime tool composition.

Called ONCE at application startup (from composition.py, alongside
register_agents/create_planner) — not per-request. Every tool built
here is a process-lifetime singleton.

This is a correction from an earlier version of this file that took
a per-request `session: AsyncSession` and `allowed_library_files_ids`
directly — that only works if register_tools() itself runs per
request, which conflicts with composition.py calling it once at
startup. A bound AsyncSession shared across concurrent requests is
not safe (SQLAlchemy sessions aren't concurrency-safe), and a bound
ACL value would leak whichever request happened to be active at
construction time onto every later request.

Per-request values (DB session lifecycle, ACL) now live at the
call boundary instead: tools take a session FACTORY (opened fresh per
method call) and read allowed_library_files_ids from
core.request_context at execute()-time. See tools/library_files/
library_file_lookup.py and tools/retrieval.py for where that actually
happens.
"""

from __future__ import annotations

from adapters.persistence.sqlalchemy.session import session_factory
from agentic.tools.library_files.file_lookup import LibraryFileLookupTool
from agentic.tools.library_files.parser import ParserTool
from agentic.tools.messaging.email import EmailTool
from agentic.tools.messaging.slack import SlackTool
from agentic.tools.retrieval import RetrieverTool
from agentic.tools.search_engine.case_law_search import CaseLawSearchTool
from agentic.tools.search_engine.web_research import WebResearchTool
from application.authorization.approval_lifecycle.protocols import (
    ApprovalLifecycleServiceProtocol,
)
from runtime.containers import ClientContainer, RegistryContainer


def register_tools(
    *,
    clients: ClientContainer,
    registries: RegistryContainer,
    approval_service: ApprovalLifecycleServiceProtocol,
) -> None:
    library_file_lookup = LibraryFileLookupTool(session_factory=session_factory)
    parser = ParserTool()

    retriever = RetrieverTool(hybrid_retriever=clients.hybrid_retriever)

    web_research = WebResearchTool(
        searxng_client=clients.searxng_client,
        content_fetcher=clients.content_fetcher,
    )

    case_law_search = CaseLawSearchTool(
        web_research_tool=web_research,
        session_factory=session_factory,
    )

    email = EmailTool(
        mcp_registry=clients.mcp_registry,
        approval_service=approval_service,
    )
    slack = SlackTool(
        mcp_registry=clients.mcp_registry,
        approval_service=approval_service,
    )

    for tool in (
        library_file_lookup,
        parser,
        retriever,
        web_research,
        case_law_search,
        email,
        slack,
    ):
        registries.tool_registry.register(component=tool)
