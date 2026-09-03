"""Unit tests for the RAG retrieval tool."""

from unittest.mock import AsyncMock

import pytest

from agentic.tools.retrieval import RetrieverTool
from application.context.request import bind_request_context


@pytest.mark.asyncio
async def test_execute_returns_safe_fallback_when_retrieval_fails() -> None:
    """A retriever failure must not break the agent execution graph."""

    hybrid_retriever = AsyncMock()
    hybrid_retriever.retrieve.side_effect = RuntimeError("reranker unavailable")
    tool = RetrieverTool(hybrid_retriever=hybrid_retriever)

    with bind_request_context() as context:
        context.allowed_document_ids = set()
        result = await tool.execute(query="payment terms")

    assert result == "Retrieval failed — please try again."
