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
from typing import Any

from adapters.observability.logger import get_logger
from core.exceptions.rag import RerankError
from rag.models import RetrievalResult
from rag.protocols.reranker import RerankerProtocol

logger = get_logger(__name__)

DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"


class CrossEncoderReranker(RerankerProtocol):
    """
    Cross-encoder implementation of the RAG reranking capability.

    The reranker operates on RetrievalResult objects so the complete
    retrieval representation is preserved throughout reranking.

    Only the relevance score is replaced.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_RERANKER_MODEL,
        raw_output_is_logit: bool = True,
    ) -> None:
        """
        Configure the cross-encoder reranker.

        Args:
            model_name:
                Cross-encoder model identifier.

            raw_output_is_logit:
                Whether model output is an unbounded logit requiring
                sigmoid normalization.
        """

        if not model_name.strip():
            raise ValueError(
                "Reranker model name cannot be empty.",
            )

        self._model_name = model_name
        self._raw_output_is_logit = raw_output_is_logit
        self._model: Any | None = None

        logger.info(
            "Configured ONNX reranker model.",
            extra={
                "model": model_name,
                "raw_output_is_logit": raw_output_is_logit,
            },
        )

    def _load(self) -> Any:
        """
        Lazily load the cross-encoder using the ONNX backend.
        """

        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import CrossEncoder

            logger.info(
                "Loading ONNX reranker model.",
                extra={
                    "model": self._model_name,
                },
            )

            self._model = CrossEncoder(
                self._model_name,
                backend="onnx",
            )

            return self._model

        except Exception as exc:
            logger.exception(
                "Failed to load ONNX reranker model.",
                extra={
                    "model": self._model_name,
                },
            )

            raise RerankError(
                message=("Failed to load ONNX reranker model " f"'{self._model_name}'."),
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

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """
        Rerank retrieval candidates using the cross-encoder.

        The existing RetrievalResult objects are preserved. Only the
        score is replaced with the normalized cross-encoder relevance
        score.

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
            model = self._load()

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

            reranked = [
                result.with_score(score)
                for result, score in zip(
                    candidates,
                    scores,
                    strict=True,
                )
            ]

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
