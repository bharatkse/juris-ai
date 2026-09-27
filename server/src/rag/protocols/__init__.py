"""
RAG capability protocols.
"""

from rag.protocols.embedding_provider import EmbeddingProviderProtocol
from rag.protocols.keyword import KeywordStoreProtocol
from rag.protocols.vector import VectorStoreProtocol

__all__ = [
    "EmbeddingProviderProtocol",
    "KeywordStoreProtocol",
    "VectorStoreProtocol",
]
