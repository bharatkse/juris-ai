"""Unit tests for the RAG retrieval tool."""

from unittest.mock import AsyncMock

import pytest

from agentic.tools.retrieval import RetrieverTool
from application.context.request import bind_request_context
from rag.models import Chunk, RetrievalResult


@pytest.mark.asyncio
async def test_execute_returns_safe_fallback_when_retrieval_fails() -> None:
    """A retriever failure must not break the agent execution graph."""

    hybrid_retriever = AsyncMock()
    hybrid_retriever.retrieve.side_effect = RuntimeError("reranker unavailable")
    tool = RetrieverTool(hybrid_retriever=hybrid_retriever)

    with bind_request_context():
        result = await tool.execute(query="payment terms")

    assert result == "Retrieval failed — please try again."


@pytest.mark.asyncio
async def test_execute_formats_successful_retrieval_results() -> None:
    """
    The success path was previously untested and silently broken
    (bugs #1/#2: tuple-unpacking a non-iterable RetrievalResult, and a
    nonexistent chunk.document_id attribute). This exercises that path
    with a real, non-empty result -- and confirms title (from bug #6's
    fix) is preferred over source when present.
    """

    chunk = Chunk(
        id="kchn_abc123",
        source="ksrc_example",
        text="Section 43 imposes penalty and compensation for damage.",
        metadata={"sequence": "2", "title": "IT Act 2000"},
    )
    result = RetrievalResult(chunk=chunk, score=0.87231)

    hybrid_retriever = AsyncMock()
    hybrid_retriever.retrieve.return_value = [result]
    tool = RetrieverTool(hybrid_retriever=hybrid_retriever)

    with bind_request_context():
        output = await tool.execute(query="penalty for damage")

    assert "IT Act 2000" in output
    assert "ksrc_example" not in output
    assert "chunk 2" in output
    assert "relevance=0.872" in output
    assert "Section 43 imposes penalty" in output


@pytest.mark.asyncio
async def test_execute_falls_back_to_source_when_title_absent() -> None:
    """
    Content indexed before bug #6's fix has no title metadata -- the
    tool must fall back to source rather than crash or print "None".
    """

    chunk = Chunk(
        id="kchn_xyz789",
        source="ksrc_legacy",
        text="Legacy chunk with no title metadata.",
        metadata={"sequence": "0"},
    )
    result = RetrievalResult(chunk=chunk, score=0.5)

    hybrid_retriever = AsyncMock()
    hybrid_retriever.retrieve.return_value = [result]
    tool = RetrieverTool(hybrid_retriever=hybrid_retriever)

    with bind_request_context():
        output = await tool.execute(query="anything")

    assert "ksrc_legacy" in output
    assert "chunk 0" in output


@pytest.mark.asyncio
async def test_execute_formats_multiple_results_without_crashing() -> None:
    """A second, unrelated result must not disturb the first."""

    results = [
        RetrievalResult(
            chunk=Chunk(
                id="kchn_1",
                source="ksrc_a",
                text="First chunk.",
                metadata={"sequence": "0"},
            ),
            score=0.9,
        ),
        RetrievalResult(
            chunk=Chunk(
                id="kchn_2",
                source="ksrc_b",
                text="Second chunk.",
                metadata={"sequence": "5"},
            ),
            score=0.5,
        ),
    ]

    hybrid_retriever = AsyncMock()
    hybrid_retriever.retrieve.return_value = results
    tool = RetrieverTool(hybrid_retriever=hybrid_retriever)

    with bind_request_context():
        output = await tool.execute(query="anything")

    assert "First chunk." in output
    assert "Second chunk." in output
    assert output.count("relevance=") == 2
