"""
Vector store capability contract.

Defines the interface required by the RAG indexing and retrieval layers.
Concrete persistence implementations, such as PGVector, implement this
protocol.
"""

from __future__ import annotations

from typing import Protocol

from rag.models import Chunk, RetrievalResult


class VectorStoreProtocol(Protocol):
    """
    Capability contract for vector storage and similarity retrieval.
    """

    async def upsert(
        self,
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        """
        Persist one bounded batch of vector representations.
        """

        ...

    async def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        embedding_model: str,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve vector-search candidates.
        """

        ...
