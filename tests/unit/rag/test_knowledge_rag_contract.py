from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from application.services.rag_index_persistence import RAGIndexPersistenceService
from rag.hybrid_retriever import HybridRetriever
from rag.keyword_store import PostgresKeywordStore
from rag.models import Chunk, RetrievalResult
from rag.pgvector_store import PgVectorStore


class _AsyncSessionContext:
    def __init__(self) -> None:
        self.session = SimpleNamespace(commit=AsyncMock())

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


@pytest.mark.asyncio
async def test_persistence_creates_knowledge_source_before_chunk(
    monkeypatch,
):
    source_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        create=AsyncMock(),
    )
    chunk_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        create=AsyncMock(),
        update=AsyncMock(),
    )
    embedding_repository = SimpleNamespace(upsert=AsyncMock())

    monkeypatch.setattr(
        "application.services.rag_index_persistence.KnowledgeSourceRepository",
        lambda session: source_repository,
    )
    monkeypatch.setattr(
        "application.services.rag_index_persistence.KnowledgeChunkRepository",
        lambda session: chunk_repository,
    )
    monkeypatch.setattr(
        "application.services.rag_index_persistence.KnowledgeEmbeddingRepository",
        lambda session: embedding_repository,
    )

    service = RAGIndexPersistenceService()
    service._session_factory = lambda: _AsyncSessionContext()

    chunk = Chunk(
        id="chunk-1",
        source_id="/approved/acts/example.pdf",
        text="Legal text.",
        metadata={"source_id": "/approved/acts/example.pdf"},
    )

    await service.persist(
        chunks=[chunk],
        vectors=[[0.1, 0.2]],
        embedding_model="test-model",
        embedding_dimension=2,
    )

    source = source_repository.create.await_args.args[0]
    assert source.id.startswith("ksrc_")
    assert chunk_repository.create.await_args.kwargs["knowledge_source_id"] == source.id
    assert "document_id" not in chunk_repository.create.await_args.kwargs
    embedding_repository.upsert.assert_awaited_once_with(
        chunk_id="chunk-1",
        embedding_model="test-model",
        vector=[0.1, 0.2],
    )


def test_retrieval_result_exposes_knowledge_source_id():
    result = RetrievalResult(
        chunk=Chunk(
            id="chunk-1",
            source_id="/approved/acts/example.pdf",
            text="Legal text.",
            metadata={"knowledge_source_id": "ksrc_example"},
        ),
        score=0.9,
    )

    assert result.knowledge_source_id == "ksrc_example"


@pytest.mark.asyncio
async def test_vector_and_keyword_results_preserve_knowledge_source_id(
    monkeypatch,
):
    embedding = SimpleNamespace(
        embedding_model="test-model",
        embedding_dimension=2,
        embedding=[0.1, 0.2],
    )
    chunk = SimpleNamespace(
        id="chunk-1",
        knowledge_source_id="ksrc_example",
        chunk_metadata={
            "source_id": "/approved/acts/example.pdf",
            "knowledge_source_id": "ksrc_example",
        },
        text="Legal text.",
        embeddings=[embedding],
    )

    class RetrievalRepository:
        def __init__(self, *, session):
            pass

        async def vector_search(self, **kwargs):
            return [(SimpleNamespace(chunk=chunk, **embedding.__dict__), 0.9)]

        async def keyword_search(self, **kwargs):
            return [(chunk, 0.8)]

    monkeypatch.setattr(
        "rag.pgvector_store.RAGRetrievalRepository",
        RetrievalRepository,
    )
    monkeypatch.setattr(
        "rag.keyword_store.RAGRetrievalRepository",
        RetrievalRepository,
    )

    vector_store = PgVectorStore(session_factory=lambda: _AsyncSessionContext())
    keyword_store = PostgresKeywordStore(session_factory=lambda: _AsyncSessionContext())

    vector_results = await vector_store.query(
        vector=[0.1, 0.2],
        top_k=1,
        embedding_model="test-model",
    )
    keyword_results = await keyword_store.query(
        query="legal",
        top_k=1,
    )

    assert vector_results[0].knowledge_source_id == "ksrc_example"
    assert keyword_results[0].knowledge_source_id == "ksrc_example"


def test_hybrid_merge_preserves_knowledge_source_id():
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever._rrf_k = 60

    result = RetrievalResult(
        chunk=Chunk(
            id="chunk-1",
            source_id="/approved/acts/example.pdf",
            text="Legal text.",
            metadata={"knowledge_source_id": "ksrc_example"},
        ),
        score=0.9,
    )

    merged = retriever._reciprocal_rank_fusion(
        ranked_lists=((result,), (result,)),
    )

    assert merged[0].knowledge_source_id == "ksrc_example"
