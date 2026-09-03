from types import SimpleNamespace
from unittest.mock import MagicMock

from rag.hybrid_retriever import HybridRetriever
from rag.indexer import RAGIndexer
from runtime.factories.rag import build_rag_pipeline


def test_build_rag_pipeline_shares_embedding_and_vector_store(monkeypatch):
    embedding_provider = MagicMock(name="embedding_provider")
    vector_store = MagicMock(name="vector_store")
    keyword_store = MagicMock(name="keyword_store")
    reranker = MagicMock(name="reranker")

    embedding_provider.metadata = SimpleNamespace(
        model_name="test-embedding",
        dimension=384,
    )

    monkeypatch.setattr(
        "runtime.factories.rag.SentenceTransformerEmbeddingProvider",
        lambda: embedding_provider,
    )
    monkeypatch.setattr(
        "runtime.factories.rag.PgVectorStore",
        lambda: vector_store,
    )
    monkeypatch.setattr(
        "runtime.factories.rag.PostgresKeywordStore",
        lambda: keyword_store,
    )
    monkeypatch.setattr(
        "runtime.factories.rag.CrossEncoderReranker",
        lambda: reranker,
    )

    settings = SimpleNamespace(
        llm=SimpleNamespace(
            rag_min_rerank_score=60,
            rag_chunk_size=32,
        ),
    )

    pipeline = build_rag_pipeline(settings=settings)

    assert isinstance(pipeline.hybrid_retriever, HybridRetriever)
    assert isinstance(pipeline.rag_indexer, RAGIndexer)

    assert pipeline.hybrid_retriever._embedding_provider is embedding_provider
    assert pipeline.hybrid_retriever._vector_store is vector_store
    assert pipeline.hybrid_retriever._keyword_store is keyword_store
    assert pipeline.hybrid_retriever._reranker is reranker

    assert pipeline.rag_indexer._embedding_provider is embedding_provider
    assert pipeline.rag_indexer._vector_store is vector_store


def test_build_rag_pipeline_creates_separate_keyword_store_and_reranker(
    monkeypatch,
):
    embedding_provider = MagicMock(name="embedding_provider")
    vector_store = MagicMock(name="vector_store")
    keyword_store = MagicMock(name="keyword_store")
    reranker = MagicMock(name="reranker")

    embedding_provider.metadata = SimpleNamespace(
        model_name="test-embedding",
        dimension=384,
    )

    embedding_factory = MagicMock(return_value=embedding_provider)
    vector_factory = MagicMock(return_value=vector_store)
    keyword_factory = MagicMock(return_value=keyword_store)
    reranker_factory = MagicMock(return_value=reranker)

    monkeypatch.setattr(
        "runtime.factories.rag.SentenceTransformerEmbeddingProvider",
        embedding_factory,
    )
    monkeypatch.setattr(
        "runtime.factories.rag.PgVectorStore",
        vector_factory,
    )
    monkeypatch.setattr(
        "runtime.factories.rag.PostgresKeywordStore",
        keyword_factory,
    )
    monkeypatch.setattr(
        "runtime.factories.rag.CrossEncoderReranker",
        reranker_factory,
    )

    settings = SimpleNamespace(
        llm=SimpleNamespace(
            rag_min_rerank_score=60,
            rag_chunk_size=32,
        ),
    )

    pipeline = build_rag_pipeline(settings=settings)

    embedding_factory.assert_called_once_with()
    vector_factory.assert_called_once_with()
    keyword_factory.assert_called_once_with()
    reranker_factory.assert_called_once_with()

    assert pipeline.hybrid_retriever._embedding_provider is embedding_provider
    assert pipeline.rag_indexer._embedding_provider is embedding_provider

    assert pipeline.hybrid_retriever._vector_store is vector_store
    assert pipeline.rag_indexer._vector_store is vector_store

    assert pipeline.hybrid_retriever._keyword_store is keyword_store
    assert pipeline.hybrid_retriever._reranker is reranker

    assert pipeline.hybrid_retriever._rrf_k == 60
    assert pipeline.rag_indexer._batch_size == 32
