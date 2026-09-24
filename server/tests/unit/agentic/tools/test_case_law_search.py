"""
Unit tests for CaseLawSearchTool.search_contracts().

Regression coverage for two fixes: the removed
RequestContext.allowed_knowledge_source_ids reference (never existed --
see the tool's own docstring for why that scope is intentionally
unrestricted, not newly unscoped), and the KnowledgeSource.title
field-reference bug (same shape as the Library.title bug fixed
alongside it).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agentic.tools.search_engine.case_law_search import CaseLawSearchTool

pytestmark = pytest.mark.asyncio


class _AsyncSessionContext:
    def __init__(self, session: object) -> None:
        self._session = session

    def __call__(self) -> _AsyncSessionContext:
        return self

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


async def test_search_contracts_does_not_touch_request_context() -> None:
    """
    search_contracts() must run without any request context bound at
    all -- it is deliberately not ACL-scoped, so it has no reason to
    call get_request_context(). Previously this raised AttributeError
    reading a RequestContext attribute that never existed; now it
    doesn't even try.
    """

    knowledge_source = SimpleNamespace(
        id="ksrc_1",
        filename="master_services_agreement.pdf",
        original_filename=None,
    )

    fake_session = object()

    with patch(
        "agentic.tools.search_engine.case_law_search.KnowledgeSourceRepository"
    ) as repository_cls:
        repository = repository_cls.return_value
        repository.search = AsyncMock(return_value=[knowledge_source])

        tool = CaseLawSearchTool(
            web_research_tool=AsyncMock(),
            session_factory=_AsyncSessionContext(fake_session),
        )

        # No bind_request_context() anywhere in this test -- if
        # search_contracts() read request context, this would raise
        # "No request context is bound."
        output = await tool.search_contracts(query="services agreement")

    assert "ksrc_1" in output
    assert "master_services_agreement.pdf" in output


async def test_search_contracts_returns_no_matches_message_when_empty() -> None:
    with patch(
        "agentic.tools.search_engine.case_law_search.KnowledgeSourceRepository"
    ) as repository_cls:
        repository = repository_cls.return_value
        repository.search = AsyncMock(return_value=[])

        tool = CaseLawSearchTool(
            web_research_tool=AsyncMock(),
            session_factory=_AsyncSessionContext(object()),
        )

        output = await tool.search_contracts(query="nothing matches this")

    assert output == "No matching contracts found."
