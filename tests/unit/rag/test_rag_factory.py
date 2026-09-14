from types import SimpleNamespace
from unittest.mock import MagicMock

from rag.hybrid_retriever import HybridRetriever
from rag.indexer import RAGIndexer
from wiring.factories.rag import build_rag_pipeline


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
        "wiring.factories.rag.SentenceTransformerEmbeddingProvider",
        lambda: embedding_provider,
    )
    monkeypatch.setattr(
        "wiring.factories.rag.PgVectorStore",
        lambda: vector_store,
    )
    monkeypatch.setattr(
        "wiring.factories.rag.PostgresKeywordStore",
        lambda: keyword_store,
    )
    monkeypatch.setattr(
        "wiring.factories.rag.CrossEncoderReranker",
        lambda: reranker,
    )

    settings = SimpleNamespace(
        llm=SimpleNamespace(
            rag_rrf_k=60,
            rag_chunk_size=32,
        ),
        security=SimpleNamespace(
            CACHE_TTL_SECONDS=604_800,
        ),
    )

    cache = MagicMock(name="cache")

    pipeline = build_rag_pipeline(settings=settings, cache=cache)

    assert isinstance(pipeline.hybrid_retriever, HybridRetriever)
    assert isinstance(pipeline.rag_indexer, RAGIndexer)

    # The shared embedding_provider is now wrapped in
    # CachingEmbeddingProvider (wiring/factories/rag.py) -- both
    # hybrid_retriever and rag_indexer must receive the SAME wrapper
    # instance (still true sharing, just one layer removed from the
    # raw mock) so caching applies uniformly across both.
    caching_provider = pipeline.hybrid_retriever._embedding_provider

    assert caching_provider._wrapped is embedding_provider
    assert caching_provider._cache is cache
    assert pipeline.hybrid_retriever._vector_store is vector_store
    assert pipeline.hybrid_retriever._keyword_store is keyword_store
    assert pipeline.hybrid_retriever._reranker is reranker

    assert pipeline.rag_indexer._embedding_provider is caching_provider
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
        "wiring.factories.rag.SentenceTransformerEmbeddingProvider",
        embedding_factory,
    )
    monkeypatch.setattr(
        "wiring.factories.rag.PgVectorStore",
        vector_factory,
    )
    monkeypatch.setattr(
        "wiring.factories.rag.PostgresKeywordStore",
        keyword_factory,
    )
    monkeypatch.setattr(
        "wiring.factories.rag.CrossEncoderReranker",
        reranker_factory,
    )

    settings = SimpleNamespace(
        llm=SimpleNamespace(
            rag_rrf_k=60,
            rag_chunk_size=32,
        ),
        security=SimpleNamespace(
            CACHE_TTL_SECONDS=604_800,
        ),
    )

    cache = MagicMock(name="cache")

    pipeline = build_rag_pipeline(settings=settings, cache=cache)

    embedding_factory.assert_called_once_with()
    vector_factory.assert_called_once_with()
    keyword_factory.assert_called_once_with()
    reranker_factory.assert_called_once_with()

    caching_provider = pipeline.hybrid_retriever._embedding_provider

    assert caching_provider._wrapped is embedding_provider
    assert pipeline.rag_indexer._embedding_provider is caching_provider

    assert pipeline.hybrid_retriever._vector_store is vector_store
    assert pipeline.rag_indexer._vector_store is vector_store

    assert pipeline.hybrid_retriever._keyword_store is keyword_store
    assert pipeline.hybrid_retriever._reranker is reranker

    assert pipeline.hybrid_retriever._rrf_k == 60
    assert pipeline.rag_indexer._batch_size == 32
