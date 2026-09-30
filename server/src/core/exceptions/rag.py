"""
RAG pipeline exceptions.
"""

from __future__ import annotations

from core.exceptions.base import AppError


class RAGError(AppError):
    """Base exception for RAG pipeline failures."""


class EmbeddingError(RAGError):
    """Embedding model failed to load or produce vectors."""


class VectorStoreError(RAGError):
    """Vector store read/write failed."""


class RetrievalUnavailableError(RAGError):
    """
    No search could run: the stores failed, or two components failed at
    once (see HybridRetriever.retrieve()). One failed component degrades
    the search instead of raising this.
    """


class RerankError(RAGError):
    """Reranking model failed."""


class SimilarityUnavailableError(RAGError):
    """
    The answer gate's embedding similarity couldn't be computed: the
    embedding model failed or took too long (review G2). The gate then
    gives the "couldn't verify" answer instead of scoring the answer.
    """
