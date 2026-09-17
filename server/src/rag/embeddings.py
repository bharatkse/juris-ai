"""
Concrete embedding implementations for the RAG data plane.

This module contains provider implementations only.

Contracts live in:
    rag.protocols.embedding_provider

Embedding metadata lives in:
    rag.models

The embedding implementation does not:
    - persist vectors
    - access PGVector
    - access BM25
    - perform retrieval
    - perform reranking
    - call an LLM
    - manage documents
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from adapters.observability.logger import get_logger
from core.exceptions.rag import EmbeddingError
from rag.models import EmbeddingMetadata
from rag.protocols.embedding_provider import EmbeddingProviderProtocol

logger = get_logger(__name__)

# Bump this if the model changes — stored alongside vectors so a
# model swap can be detected instead of silently mixing incompatible
# embedding spaces (see EMBEDDING_MODEL_VERSION usage in indexer.py).
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_EMBEDDING_DIMENSION = 384
DEFAULT_MAX_BATCH_SIZE = 64


class SentenceTransformerEmbeddingProvider(EmbeddingProviderProtocol):
    """
    Local embedding provider backed by sentence-transformers.

    The model is loaded lazily and shared by embedding operations.

    The provider is stateless with respect to documents. It stores only
    provider configuration and the loaded model instance.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
    ) -> None:
        """
        Configure the local embedding provider.

        Args:
            model_name:
                Sentence-transformers model identifier.

            dimension:
                Expected vector dimension.

            max_batch_size:
                Maximum number of texts processed by one model call.
        """

        if not model_name.strip():
            raise ValueError(
                "Embedding model name cannot be empty.",
            )

        if dimension <= 0:
            raise ValueError(
                "Embedding dimension must be greater than zero.",
            )

        if max_batch_size <= 0:
            raise ValueError(
                "Embedding batch size must be greater than zero.",
            )

        self._metadata = EmbeddingMetadata(
            model_name=model_name,
            dimension=dimension,
        )

        self._max_batch_size = max_batch_size
        self._model: Any | None = None
        self._model_lock = threading.Lock()

        logger.info(
            "Configured embedding provider.",
            extra={
                "model": self.metadata.model_name,
                "dimension": self.metadata.dimension,
                "max_batch_size": self._max_batch_size,
            },
        )

    @property
    def metadata(self) -> EmbeddingMetadata:
        """
        Return metadata describing the embedding representation.
        """

        return self._metadata

    def _load(self) -> Any:
        """
        Lazily load the sentence-transformers model.

        Model loading is protected so concurrent worker threads do not
        initialize multiple model instances.
        """

        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is not None:
                return self._model

            try:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    "Loading embedding model.",
                    extra={
                        "model": self.metadata.model_name,
                    },
                )

                model = SentenceTransformer(
                    self.metadata.model_name,
                )

                actual_dimension = model.get_sentence_embedding_dimension()

                if actual_dimension is None or actual_dimension <= 0:
                    raise EmbeddingError(
                        message=("Embedding model returned an invalid " "vector dimension."),
                    )

                if actual_dimension != self.metadata.dimension:
                    raise EmbeddingError(
                        message=(
                            "Embedding dimension mismatch for model "
                            f"'{self.metadata.model_name}': configured "
                            f"{self.metadata.dimension}, model produces "
                            f"{actual_dimension}."
                        ),
                    )

                self._model = model

                logger.info(
                    "Embedding model loaded successfully.",
                    extra={
                        "model": self.metadata.model_name,
                        "dimension": self.metadata.dimension,
                    },
                )

                return model

            except EmbeddingError:
                logger.exception(
                    "Embedding model validation failed.",
                    extra={
                        "model": self.metadata.model_name,
                    },
                )
                raise

            except Exception as exc:
                logger.exception(
                    "Failed to load embedding model.",
                    extra={
                        "model": self.metadata.model_name,
                    },
                )

                raise EmbeddingError(
                    message=("Failed to load embedding model " f"'{self.metadata.model_name}'."),
                ) from exc

    def _encode_batch(
        self,
        batch: list[str],
    ) -> list[list[float]]:
        """
        Encode one bounded batch synchronously.

        sentence-transformers is synchronous, so the public async API
        executes this method in a worker thread.
        """

        if not batch:
            return []

        try:
            model = self._load()

            encoded = model.encode(
                batch,
                normalize_embeddings=True,
            )

            vectors = [vector.tolist() for vector in encoded]

            self._validate_vectors(
                vectors=vectors,
                expected_count=len(batch),
            )

            return vectors

        except EmbeddingError:
            raise

        except Exception as exc:
            logger.exception(
                "Failed to encode embedding batch.",
                extra={
                    "model": self.metadata.model_name,
                    "batch_size": len(batch),
                },
            )

            raise EmbeddingError(
                message=(
                    "Failed to encode embedding batch using model " f"'{self.metadata.model_name}'."
                ),
            ) from exc

    def _validate_vectors(
        self,
        *,
        vectors: list[list[float]],
        expected_count: int,
    ) -> None:
        """
        Validate embedding count and dimensions.
        """

        if len(vectors) != expected_count:
            raise EmbeddingError(
                message=(
                    "Embedding count mismatch for model "
                    f"'{self.metadata.model_name}': expected "
                    f"{expected_count}, received {len(vectors)}."
                ),
            )

        for index, vector in enumerate(vectors):
            if len(vector) != self.metadata.dimension:
                raise EmbeddingError(
                    message=(
                        "Invalid embedding dimension for model "
                        f"'{self.metadata.model_name}' at index "
                        f"{index}: expected "
                        f"{self.metadata.dimension}, received "
                        f"{len(vector)}."
                    ),
                )

    async def embed(
        self,
        *,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Input is processed in bounded batches and output vectors
        preserve the input order.
        """

        if not texts:
            return []

        for index, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbeddingError(
                    message=("Cannot generate an embedding for empty text " f"at index {index}."),
                )

        vectors: list[list[float]] = []

        try:
            for start in range(
                0,
                len(texts),
                self._max_batch_size,
            ):
                batch = texts[start : start + self._max_batch_size]

                batch_vectors = await asyncio.to_thread(
                    self._encode_batch,
                    batch,
                )

                vectors.extend(batch_vectors)

            self._validate_vectors(
                vectors=vectors,
                expected_count=len(texts),
            )

            logger.debug(
                "Generated embeddings.",
                extra={
                    "model": self.metadata.model_name,
                    "text_count": len(texts),
                },
            )

            return vectors

        except EmbeddingError:
            logger.exception(
                "Embedding generation failed.",
                extra={
                    "model": self.metadata.model_name,
                    "text_count": len(texts),
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected embedding generation failure.",
                extra={
                    "model": self.metadata.model_name,
                    "text_count": len(texts),
                },
            )

            raise EmbeddingError(
                message=(
                    "Failed to generate embeddings using model " f"'{self.metadata.model_name}'."
                ),
            ) from exc

    async def embed_one(
        self,
        *,
        text: str,
    ) -> list[float]:
        """
        Generate an embedding for a single retrieval query.
        """

        if not text or not text.strip():
            raise EmbeddingError(
                message="Cannot generate an embedding for empty text.",
            )

        try:
            vectors = await self.embed(
                texts=[text],
            )

            if len(vectors) != 1:
                raise EmbeddingError(
                    message=(
                        "Embedding provider returned an invalid "
                        "number of vectors for a single query."
                    ),
                )

            return vectors[0]

        except EmbeddingError:
            logger.exception(
                "Query embedding generation failed.",
                extra={
                    "model": self.metadata.model_name,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected query embedding failure.",
                extra={
                    "model": self.metadata.model_name,
                },
            )

            raise EmbeddingError(
                message=(
                    "Failed to generate query embedding using model "
                    f"'{self.metadata.model_name}'."
                ),
            ) from exc
