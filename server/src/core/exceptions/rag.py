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


class RerankError(RAGError):
    """Reranking model failed."""
