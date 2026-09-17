"""
Embedding provider capability contract.

Defines the interface used by the RAG indexing and retrieval layers
without coupling them to a concrete embedding implementation.
"""

from __future__ import annotations

from typing import Protocol

from rag.models import EmbeddingMetadata


class EmbeddingProviderProtocol(Protocol):
    """
    Provider-independent embedding capability.
    """

    @property
    def metadata(self) -> EmbeddingMetadata:
        """
        Return metadata describing the embedding representation.
        """

        ...

    async def embed(
        self,
        *,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Returned vectors must preserve input order.
        """

        ...

    async def embed_one(
        self,
        *,
        text: str,
    ) -> list[float]:
        """
        Generate an embedding for a single query.
        """

        ...
