"""
RAG pipeline composition.

Builds the embedding model, reranker model, HybridRetriever (query
path), and RAGIndexer (ingestion path) ONCE, at application
startup.

Critical: HybridRetriever and RAGIndexer must share the SAME
EmbeddingProvider instance, not one each. The embedding model is
process-lifetime and expensive to load — two separate
SentenceTransformerEmbeddingProvider() instances would each lazy-load
their own copy of the model into memory the first time they're used,
doubling memory for zero benefit. This was a real risk the first time
RAGIndexer was going to be wired in, since factories/rag.py only
ever built one for HybridRetriever.

PgVectorStore is cheap (just holds session_factory) so sharing one
instance between retriever and indexer isn't required for the same
reason, but is still done here for consistency — one object graph,
not two parallel ones touching the same table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rag.embeddings import SentenceTransformerEmbeddingProvider
from rag.hybrid_retriever import HybridRetriever
from rag.indexer import RAGIndexer
from rag.keyword_store import PostgresKeywordStore
from rag.pgvector_store import PgVectorStore
from rag.reranker import CrossEncoderReranker

if TYPE_CHECKING:
    from config.settings import Settings


@dataclass(frozen=True, slots=True)
class RAGPipeline:
    """
    Groups the query-path and ingestion-path entry points that share
    the same underlying models/store — built together so that sharing
    is structural (one function builds both), not just a convention
    someone has to remember to follow.
    """

    hybrid_retriever: HybridRetriever
    rag_indexer: RAGIndexer


def build_rag_pipeline(*, settings: Settings) -> RAGPipeline:
    # Built ONCE, shared by both the retriever and the indexer below.
    embedding_provider = SentenceTransformerEmbeddingProvider()
    vector_store = PgVectorStore()

    hybrid_retriever = HybridRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        keyword_store=PostgresKeywordStore(),
        reranker=CrossEncoderReranker(),
        rrf_k=settings.llm.rag_min_rerank_score,
    )

    rag_indexer = RAGIndexer(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        batch_size=settings.llm.rag_chunk_size,
    )

    return RAGPipeline(
        hybrid_retriever=hybrid_retriever,
        rag_indexer=rag_indexer,
    )
