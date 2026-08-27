"""
Embedding provider.

Wraps whichever embedding model/API produces vectors for RAG
indexing and querying. Kept as its own small class so the vector
store implementation and the embedding source can vary independently.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from adapters.observability.logger import get_logger
from core.exceptions.rag import EmbeddingError

log = get_logger(__name__)

# Bump this if the model changes — stored alongside vectors so a
# model swap can be detected instead of silently mixing incompatible
# embedding spaces (see EMBEDDING_MODEL_VERSION usage in indexer.py).
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
_MAX_BATCH_SIZE = 64  # avoid unbounded memory use on very large documents


class EmbeddingProvider(ABC):
    """
    Abstract embedding provider.
    """

    model_name: str
    dimension: int

    @abstractmethod
    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of texts. Returns one vector per input text, in
        the same order.
        """
        raise NotImplementedError

    @abstractmethod
    async def embed_one(self, *, text: str) -> list[float]:
        """
        Embed a single text (e.g. a query at retrieval time).
        """
        raise NotImplementedError


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """
    Local embedding provider using sentence-transformers.

    Runs on CPU/GPU alongside the local LLM — no external API call,
    keeping RAG queries fast and free of per-call cost.
    """

    def __init__(
        self,
        *,
        model_name: str = EMBEDDING_MODEL_NAME,
        dimension: int = EMBEDDING_DIM,
        max_batch_size: int = _MAX_BATCH_SIZE,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._max_batch_size = max_batch_size
        self._model = None  # lazy-loaded

        log.info("Configured local embedding model '%s'.", model_name)

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                log.info("Loading embedding model '%s'.", self.model_name)
                self._model = SentenceTransformer(self.model_name)

            except Exception as exc:
                log.exception("Failed to load embedding model '%s'.", self.model_name)
                raise EmbeddingError(
                    message=f"Failed to load embedding model '{self.model_name}'."
                ) from exc

        return self._model

    def _encode_batch(self, batch: list[str]) -> list[list[float]]:
        model = self._load()
        encoded = model.encode(batch, normalize_embeddings=True)
        return [vector.tolist() for vector in encoded]

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), self._max_batch_size):
                batch = texts[start : start + self._max_batch_size]
                batch_vectors = await asyncio.to_thread(self._encode_batch, batch)
                vectors.extend(batch_vectors)
        except Exception as exc:
            log.exception("Embedding failed for a batch of %d text(s).", len(texts))
            raise EmbeddingError(message="Failed to compute embeddings.") from exc

        return vectors

    async def embed_one(self, *, text: str) -> list[float]:
        vectors = await self.embed(texts=[text])
        if not vectors:
            raise EmbeddingError(message="Embedding returned no result for query.")
        return vectors[0]
