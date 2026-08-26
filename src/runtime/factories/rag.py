"""
RAG pipeline composition.

Builds the embedding model, reranker model, and HybridRetriever ONCE,
at application startup — called from factories/clients.py, not from
factories/tools.py. This matters: factories/tools.py runs per-request
(it needs a per-request session), so if the embedding/reranker models
lived there, each request would pay their lazy-load cost from
scratch — the actual sentence-transformers/onnxruntime model load
time, on every single request, not once.

PgVectorStore and KeywordStore are cheap (just hold a reference to
the module-level session_factory) so building them here vs. per-
request doesn't matter much either way — built here for consistency,
since they're part of the same pipeline object graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.rag.embeddings import SentenceTransformerEmbeddingProvider
from src.rag.hybrid_retriever import HybridRetriever
from src.rag.keyword_store import KeywordStore
from src.rag.pgvector_store import PgVectorStore
from src.rag.reranker import CrossEncoderReranker

if TYPE_CHECKING:
    from src.core.config import Settings


def build_hybrid_retriever(*, settings: Settings) -> HybridRetriever:
    embedding_provider = SentenceTransformerEmbeddingProvider()
    reranker = CrossEncoderReranker()

    return HybridRetriever(
        embedding_provider=embedding_provider,
        vector_store=PgVectorStore(),
        keyword_store=KeywordStore(),
        reranker=reranker,
        min_rerank_score=settings.rag_min_rerank_score,
    )
