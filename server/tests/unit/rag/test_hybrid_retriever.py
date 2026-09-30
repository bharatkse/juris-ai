"""
Unit tests: HybridRetriever degrades instead of failing (review R4).

One failed component leaves a working search: the reranker down → the
fused order, rescaled to [0, 1]; the embeddings or the vector store down →
keyword-only; the keyword store down → vector-only. With two components
down, or no store answering, retrieval is unavailable: RetrievalUnavailableError,
which RetrieverTool turns into a non-evidence result instead of raising.

The mode each search ran in (full, no_rerank, keyword_only, vector_only,
unavailable) is recorded as a metric and on the span. Every mode's scores
reach the agent's prompt as "relevance=" and must stay in [0, 1].
"""

from __future__ import annotations

import asyncio
import logging
import re
from unittest.mock import patch

import pytest

from agentic.tools.retrieval import (
    NON_EVIDENCE_CONTENT,
    RETRIEVAL_UNAVAILABLE_CONTENT,
    RetrieverTool,
)
from core.exceptions.rag import RetrievalUnavailableError
from rag import hybrid_retriever as module
from rag.hybrid_retriever import HybridRetriever
from rag.models import Chunk, RetrievalResult


def _result(chunk_id: str, score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(id=chunk_id, text=f"text {chunk_id}", metadata={"sequence": "1"}, source="act"),
        score=score,
    )


class _Metadata:
    model_name = "test-embedder"


class _Embedder:
    metadata = _Metadata()

    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    async def embed_one(self, *, text: str) -> list[float]:
        if self.fails:
            raise RuntimeError("embedding model unavailable")
        return [0.1, 0.2]


class _VectorStore:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.queried = False

    async def query(self, *, vector, top_k, embedding_model):
        self.queried = True
        if self.fails:
            raise RuntimeError("vector store unavailable")
        # Cosine similarities: not on the reranker's scale.
        return [_result("a", 0.91), _result("b", 0.87), _result("c", 0.52)]


class _KeywordStore:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    async def query(self, *, query, top_k):
        if self.fails:
            raise RuntimeError("keyword store unavailable")
        # ts_rank scores: unbounded, not on the reranker's scale either.
        return [_result("b", 3.7), _result("d", 2.2), _result("a", 1.4)]


class _Reranker:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.candidates: list[str] = []

    async def rerank(self, *, query, candidates, top_k):
        if self.fails:
            raise RuntimeError("reranker model unavailable")
        self.candidates = [result.chunk.id for result in candidates]
        scored = [result.with_score(0.9 - 0.1 * i) for i, result in enumerate(candidates)]
        return scored[:top_k]


def _retriever(
    *,
    embedding: bool = True,
    vector: bool = True,
    keyword: bool = True,
    rerank: bool = True,
) -> tuple[HybridRetriever, _VectorStore, _Reranker]:
    vector_store = _VectorStore(fails=not vector)
    reranker = _Reranker(fails=not rerank)
    retriever = HybridRetriever(
        embedding_provider=_Embedder(fails=not embedding),
        vector_store=vector_store,
        keyword_store=_KeywordStore(fails=not keyword),
        reranker=reranker,
    )
    return retriever, vector_store, reranker


@pytest.fixture
def modes():
    recorded: list[str] = []
    with patch.object(
        module.metrics, "record_retrieval", side_effect=lambda *, mode: recorded.append(mode)
    ):
        yield recorded


async def test_full_search_reranks_both_stores(modes: list[str]) -> None:
    retriever, _, reranker = _retriever()

    results = await retriever.retrieve(query="Section 66", top_k=3)

    # The reranker gets every fused candidate; the fake keeps their order.
    assert reranker.candidates == ["b", "a", "d", "c"]
    assert [r.chunk.id for r in results] == ["b", "a", "d"]
    assert modes == ["full"]


async def test_a_reranker_failure_falls_back_to_the_fused_order(
    modes: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    retriever, _, _ = _retriever(rerank=False)

    with caplog.at_level(logging.WARNING):
        results = await retriever.retrieve(query="Section 66", top_k=3)

    # RRF: a and b are in both lists, b ranks higher overall.
    assert [r.chunk.id for r in results] == ["b", "a", "d"]
    assert all(0.0 <= r.score <= 1.0 for r in results)
    assert results[0].score > results[1].score > results[2].score
    assert modes == ["no_rerank"]
    assert "reranker model unavailable" not in caplog.text  # cause by type, no content
    assert any(
        "Reranking failed" in r.message and r.levelno == logging.WARNING for r in caplog.records
    )


async def test_an_embedding_failure_searches_by_keyword_only(
    modes: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    retriever, vector_store, reranker = _retriever(embedding=False)

    with caplog.at_level(logging.WARNING):
        results = await retriever.retrieve(query="Section 66", top_k=3)

    assert not vector_store.queried
    assert reranker.candidates == ["b", "d", "a"]
    assert [r.chunk.id for r in results] == ["b", "d", "a"]
    assert modes == ["keyword_only"]
    assert any("Query embedding failed" in r.message for r in caplog.records)


async def test_a_vector_store_failure_searches_by_keyword_only(modes: list[str]) -> None:
    retriever, _, reranker = _retriever(vector=False)

    await retriever.retrieve(query="Section 66", top_k=3)

    assert reranker.candidates == ["b", "d", "a"]
    assert modes == ["keyword_only"]


async def test_a_keyword_store_failure_searches_by_vector_only(modes: list[str]) -> None:
    retriever, _, reranker = _retriever(keyword=False)

    await retriever.retrieve(query="Section 66", top_k=3)

    assert reranker.candidates == ["a", "b", "c"]
    assert modes == ["vector_only"]


@pytest.mark.parametrize(
    "down",
    [
        {"embedding": False, "rerank": False},
        {"vector": False, "keyword": False},
        {"embedding": False, "keyword": False},
        {"keyword": False, "rerank": False},
    ],
    ids=["embeddings+reranker", "both-stores", "embeddings+keyword", "keyword+reranker"],
)
async def test_two_failures_make_retrieval_unavailable(
    modes: list[str], down: dict[str, bool]
) -> None:
    retriever, _, _ = _retriever(**down)

    with pytest.raises(RetrievalUnavailableError):
        await retriever.retrieve(query="Section 66", top_k=3)

    assert modes == ["unavailable"]


async def test_cancellation_is_never_turned_into_a_degraded_search() -> None:
    retriever, vector_store, _ = _retriever()

    async def cancelled(**_kwargs):
        raise asyncio.CancelledError

    vector_store.query = cancelled

    with pytest.raises(asyncio.CancelledError):
        await retriever.retrieve(query="Section 66", top_k=3)


async def test_the_tool_reports_unavailable_retrieval_as_non_evidence(modes: list[str]) -> None:
    retriever, _, _ = _retriever(embedding=False, rerank=False)

    content = await RetrieverTool(hybrid_retriever=retriever).execute(query="Section 66")

    assert content == RETRIEVAL_UNAVAILABLE_CONTENT
    assert content in NON_EVIDENCE_CONTENT


@pytest.mark.parametrize(
    "down",
    [{}, {"rerank": False}, {"embedding": False}, {"vector": False}, {"keyword": False}],
    ids=["full", "no_rerank", "embeddings-down", "vector-down", "keyword-down"],
)
async def test_relevance_in_the_prompt_stays_in_range_in_every_mode(
    modes: list[str], down: dict[str, bool]
) -> None:
    retriever, _, _ = _retriever(**down)

    content = await RetrieverTool(hybrid_retriever=retriever).execute(query="Section 66", top_k=5)

    relevances = [float(value) for value in re.findall(r"relevance=([0-9.]+)", content)]
    assert relevances, content
    assert all(0.0 <= value <= 1.0 for value in relevances), relevances
