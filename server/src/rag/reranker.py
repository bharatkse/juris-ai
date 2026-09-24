"""
Cross-encoder reranker.

Vector and keyword retrieval provide fast, coarse candidate sets.
The cross-encoder performs second-stage reranking by evaluating the
query and each candidate chunk jointly.

Pipeline:

    VectorStore.query()
          \
           → HybridRetriever → RRF → CrossEncoderReranker
          /
    KeywordStore.query()

The reranker changes only the relevance score of RetrievalResult.

It does NOT:

    - generate embeddings
    - perform vector retrieval
    - perform keyword retrieval
    - perform RRF fusion
    - remove embedding representations
    - manage persistence
    - call an LLM
    - execute agents
"""

from __future__ import annotations

import asyncio
import math
import threading
from typing import Any

from adapters.observability.logger import get_logger
from core.exceptions.rag import RerankError
from rag.models import RetrievalResult
from rag.protocols.reranker import RerankerProtocol

logger = get_logger(__name__)

DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"
DEFAULT_RETRIEVAL_WEIGHT = 0.20


class CrossEncoderReranker(RerankerProtocol):
    """
    Cross-encoder implementation of the RAG reranking capability.

    The reranker operates on RetrievalResult objects so the complete
    retrieval representation is preserved throughout reranking.

    The final ranking combines:

        80% cross-encoder relevance
        20% original retrieval rank

    This prevents the cross-encoder from completely discarding strong
    first-stage retrieval signals from vector/keyword/RRF retrieval.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_RERANKER_MODEL,
        raw_output_is_logit: bool = True,
        retrieval_weight: float = DEFAULT_RETRIEVAL_WEIGHT,
    ) -> None:
        """
        Configure the cross-encoder reranker.

        Args:
            model_name:
                Cross-encoder model identifier.

            raw_output_is_logit:
                Whether model output is an unbounded logit requiring
                sigmoid normalization.

            retrieval_weight:
                Weight assigned to the original retrieval ranking.
                The remaining weight is assigned to the cross-encoder.
        """

        if not model_name.strip():
            raise ValueError(
                "Reranker model name cannot be empty.",
            )

        if not 0.0 <= retrieval_weight <= 1.0:
            raise ValueError(
                "retrieval_weight must be between 0.0 and 1.0.",
            )

        self._model_name = model_name
        self._raw_output_is_logit = raw_output_is_logit
        self._retrieval_weight = retrieval_weight
        self._model: Any | None = None
        self._model_lock = threading.Lock()

        logger.info(
            "Configured reranker model.",
            extra={
                "model": model_name,
                "raw_output_is_logit": raw_output_is_logit,
                "retrieval_weight": retrieval_weight,
            },
        )

    def _load(self) -> Any:
        """
        Lazily load the cross-encoder (sentence-transformers' default
        torch backend).

        Not backend="onnx": that backend needs optimum-onnx, whose
        latest release (0.1.0) caps transformers <4.58, and
        transformers <5.10 carries unfixed HIGH CVEs (CVE-2026-4372,
        CVE-2026-9856). Same model weights, so scores match the ONNX
        backend to float tolerance.

        Model loading is protected so concurrent worker threads do not
        initialize multiple model instances -- same double-checked
        locking as SentenceTransformerEmbeddingProvider._load()
        (rag/embeddings.py), reused as-is rather than a new pattern.
        Callers must invoke this via asyncio.to_thread(), same as
        embeddings.py's call site does -- this method itself stays
        synchronous so it can run in a worker thread.
        """

        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is not None:
                return self._model

            try:
                from sentence_transformers import CrossEncoder

                logger.info(
                    "Loading reranker model.",
                    extra={
                        "model": self._model_name,
                    },
                )

                self._model = CrossEncoder(self._model_name)

                return self._model

            except Exception as exc:
                logger.exception(
                    "Failed to load reranker model.",
                    extra={
                        "model": self._model_name,
                    },
                )

                raise RerankError(
                    message=("Failed to load reranker model " f"'{self._model_name}'."),
                ) from exc

    def _normalize_score(
        self,
        value: float,
    ) -> float:
        """
        Normalize model output into a [0, 1] relevance score.
        """

        if not self._raw_output_is_logit:
            return max(
                0.0,
                min(1.0, value),
            )

        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)

        z = math.exp(value)
        return z / (1.0 + z)

    @staticmethod
    def _retrieval_rank_score(
        *,
        rank: int,
        candidate_count: int,
    ) -> float:
        """
        Convert the original retrieval rank into a normalized [0, 1]
        score.

        The first candidate receives 1.0 and the last candidate receives
        0.0 when multiple candidates are present.
        """

        return 1.0 - ((rank - 1) / max(candidate_count - 1, 1))

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """
        Rerank retrieval candidates using the cross-encoder.

        The existing RetrievalResult objects are preserved. The final
        score combines the normalized cross-encoder relevance with the
        original retrieval rank.

        Args:
            query:
                User/search query.

            candidates:
                Retrieval candidates produced by vector/keyword
                retrieval and RRF fusion.

            top_k:
                Maximum number of results to return.

        Returns:
            Top-k reranked RetrievalResult objects.

        Raises:
            RerankError:
                If reranking fails.
        """

        if not candidates or top_k <= 0:
            return []

        if not query or not query.strip():
            return []

        try:
            # Offloaded like the predict() call below -- _load() does
            # a real, one-time model download/instantiation (the
            # "30-40s cold load"), which would otherwise run
            # synchronously on the event loop and block every other
            # concurrent request for its entire duration.
            model = await asyncio.to_thread(self._load)

            pairs = [
                (
                    query,
                    result.chunk.text,
                )
                for result in candidates
            ]

            raw_scores = await asyncio.to_thread(
                model.predict,
                pairs,
                convert_to_numpy=True,
            )

            scores = [
                self._normalize_score(
                    float(score),
                )
                for score in raw_scores
            ]

            if len(scores) != len(candidates):
                raise RerankError(
                    message=(
                        "Reranker score count mismatch: "
                        f"expected {len(candidates)}, "
                        f"received {len(scores)}."
                    ),
                )

            candidate_count = len(candidates)
            reranked: list[RetrievalResult] = []

            for rank, (
                result,
                cross_encoder_score,
            ) in enumerate(
                zip(
                    candidates,
                    scores,
                    strict=True,
                ),
                start=1,
            ):
                retrieval_score = self._retrieval_rank_score(
                    rank=rank,
                    candidate_count=candidate_count,
                )

                combined_score = (
                    1.0 - self._retrieval_weight
                ) * cross_encoder_score + self._retrieval_weight * retrieval_score

                reranked.append(
                    result.with_score(
                        combined_score,
                    ),
                )

            reranked.sort(
                key=lambda result: result.score,
                reverse=True,
            )

            return reranked[:top_k]

        except RerankError:
            logger.exception(
                "Reranking failed.",
                extra={
                    "candidate_count": len(candidates),
                    "top_k": top_k,
                },
            )
            raise

        except asyncio.CancelledError:
            logger.warning(
                "Reranking cancelled.",
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected reranking failure.",
                extra={
                    "candidate_count": len(candidates),
                    "top_k": top_k,
                },
            )

            raise RerankError(
                message="Reranking failed.",
            ) from exc
