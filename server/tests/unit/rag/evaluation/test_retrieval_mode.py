"""
Unit tests: the golden-set evaluation runs in the retrieval mode it asks
for, or fails.

HybridRetriever degrades on a component failure (review R4), which is
right for users but hides a broken eval: with the embedding model down,
the eval silently measures keyword-only search. ModeCheckedRetriever
records each component's failures and raises RetrievalModeError, naming
the underlying exception, as soon as a search runs in any other mode.
The degraded modes are evaluated by disabling a component on purpose.
"""

from __future__ import annotations

import pytest

from rag.evaluation.retrieval_mode import (
    ModeCheckedRetriever,
    RetrievalModeError,
    format_step_summary,
)
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
        self.calls = 0

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        return [await self.embed_one(text=text) for text in texts]

    async def embed_one(self, *, text: str) -> list[float]:
        self.calls += 1
        if self.fails:
            raise ConnectionError("Error 111 connecting to localhost:6379.")
        return [0.1, 0.2]


class _VectorStore:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    async def upsert(self, **_: object) -> None:
        return None

    async def query(self, *, vector, top_k, embedding_model):
        if self.fails:
            raise RuntimeError("vector store unavailable")
        return [_result("a", 0.91), _result("b", 0.87)]


class _KeywordStore:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    async def query(self, *, query, top_k):
        if self.fails:
            raise RuntimeError("keyword store unavailable")
        return [_result("b", 3.7), _result("d", 2.2)]


class _Reranker:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.calls = 0

    async def rerank(self, *, query, candidates, top_k):
        self.calls += 1
        if self.fails:
            raise RuntimeError("reranker model unavailable")
        return [RetrievalResult(chunk=c.chunk, score=0.9) for c in candidates][:top_k]


def _retriever(
    mode: str,
    *,
    embedder: _Embedder | None = None,
    vector_store: _VectorStore | None = None,
    keyword_store: _KeywordStore | None = None,
    reranker: _Reranker | None = None,
) -> ModeCheckedRetriever:
    return ModeCheckedRetriever.build(
        mode=mode,
        embedding_provider=embedder or _Embedder(),
        vector_store=vector_store or _VectorStore(),
        keyword_store=keyword_store or _KeywordStore(),
        reranker=reranker or _Reranker(),
        rrf_k=60,
    )


async def test_full_mode_with_every_component_up_returns_results() -> None:
    retriever = _retriever("full")

    results = await retriever.retrieve(query="right to equality", top_k=2)

    assert [r.chunk.id for r in results] == ["b", "a"]
    assert retriever.modes_used == {"full": 1}


def test_the_checked_retriever_wraps_a_real_hybrid_retriever() -> None:
    assert isinstance(_retriever("full").retriever, HybridRetriever)


async def test_full_mode_fails_on_an_embedding_error_naming_the_cause() -> None:
    retriever = _retriever("full", embedder=_Embedder(fails=True))

    with pytest.raises(RetrievalModeError) as raised:
        await retriever.retrieve(query="right to equality", top_k=2)

    message = str(raised.value)
    assert "requested full" in message
    assert "keyword_only" in message
    assert "embedding" in message
    assert "ConnectionError" in message
    assert "Error 111 connecting to localhost:6379." in message
    assert isinstance(raised.value.__cause__, ConnectionError)


@pytest.mark.parametrize(
    ("component", "used"),
    [("vector_store", "keyword_only"), ("keyword_store", "vector_only"), ("reranker", "no_rerank")],
)
async def test_full_mode_fails_on_any_other_component_error(component: str, used: str) -> None:
    broken = {
        "vector_store": _VectorStore(fails=True),
        "keyword_store": _KeywordStore(fails=True),
        "reranker": _Reranker(fails=True),
    }[component]
    retriever = _retriever("full", **{component: broken})

    with pytest.raises(RetrievalModeError) as raised:
        await retriever.retrieve(query="q", top_k=2)

    assert f"used {used}" in str(raised.value)
    assert retriever.modes_used == {}


async def test_full_mode_fails_when_retrieval_is_unavailable() -> None:
    retriever = _retriever(
        "full", embedder=_Embedder(fails=True), keyword_store=_KeywordStore(fails=True)
    )

    with pytest.raises(RetrievalModeError) as raised:
        await retriever.retrieve(query="q", top_k=2)

    assert "used unavailable" in str(raised.value)


async def test_keyword_only_mode_never_calls_the_embedding_model() -> None:
    embedder = _Embedder()
    retriever = _retriever("keyword_only", embedder=embedder)

    results = await retriever.retrieve(query="q", top_k=2)

    assert embedder.calls == 0
    assert {r.chunk.id for r in results} == {"b", "d"}
    assert retriever.modes_used == {"keyword_only": 1}


async def test_keyword_only_mode_fails_if_the_keyword_store_also_fails() -> None:
    retriever = _retriever("keyword_only", keyword_store=_KeywordStore(fails=True))

    with pytest.raises(RetrievalModeError) as raised:
        await retriever.retrieve(query="q", top_k=2)

    assert "keyword store unavailable" in str(raised.value)


async def test_no_rerank_mode_never_calls_the_reranker() -> None:
    reranker = _Reranker()
    retriever = _retriever("no_rerank", reranker=reranker)

    results = await retriever.retrieve(query="q", top_k=2)

    assert reranker.calls == 0
    assert results
    assert retriever.modes_used == {"no_rerank": 1}


async def test_no_rerank_mode_fails_if_the_embedding_model_also_fails() -> None:
    retriever = _retriever("no_rerank", embedder=_Embedder(fails=True))

    with pytest.raises(RetrievalModeError) as raised:
        await retriever.retrieve(query="q", top_k=2)

    assert "ConnectionError" in str(raised.value)


def test_an_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="vector_only"):
        _retriever("vector_only")


async def test_the_step_summary_reports_the_modes_used_and_scores() -> None:
    retriever = _retriever("full")
    await retriever.retrieve(query="q", top_k=2)

    summary = format_step_summary(
        mode="full",
        modes_used=retriever.modes_used,
        case_count=1,
        passed_cases=1,
        pass_rate=1.0,
        mean_scores={"recall@5": 0.75, "mrr": 0.5},
        min_pass_rate=65.0,
    )

    assert "### Retrieval eval: `full`" in summary
    assert "| Mode used | full (1/1 queries) |" in summary
    assert "| Pass rate | 100.00% (gate 65.0%: passed) |" in summary
    assert "| recall@5 | 0.7500 |" in summary


def test_a_non_gating_summary_says_so() -> None:
    summary = format_step_summary(
        mode="no_rerank",
        modes_used={"no_rerank": 29},
        case_count=29,
        passed_cases=20,
        pass_rate=0.6897,
        mean_scores={},
        min_pass_rate=None,
    )

    assert "| Pass rate | 68.97% (not gating) |" in summary
