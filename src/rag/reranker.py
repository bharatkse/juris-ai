"""
Cross-encoder reranker.

Vector/keyword search (and their RRF fusion) are both fast, coarse
first-pass retrievers — good at narrowing millions of chunks to a few
dozen candidates, but their relevance signal is noisier than actually
reading query+chunk together.

A cross-encoder reads the (query, chunk) pair jointly and scores
relevance directly — the standard second-stage "retrieve many, rerank
few" pattern, and the difference between "top-5 by embedding similarity"
and "top-5 the LLM should actually see" in practice.

Uses BAAI/bge-reranker-base — same model family as the embedding
provider (BAAI/bge-small-en-v1.5), local, no additional API cost.

The ONNX backend is used so the RAG MCP server does not require
PyTorch at runtime.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from src.core.exceptions.rag import RerankError
from src.core.logger import get_logger
from src.rag.indexer import Chunk

log = get_logger(__name__)

DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"


class CrossEncoderReranker:
    """
    Reranks candidate chunks against a query using an ONNX
    cross-encoder.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_RERANKER_MODEL,
        raw_output_is_logit: bool = True,
    ) -> None:
        """
        raw_output_is_logit: whether model.predict() returns an
        unbounded logit needing a manual sigmoid, or an
        already-bounded [0,1] score (some ONNX export variants bake
        the sigmoid into the graph).

        This MUST be determined once, empirically — inspect
        model.predict() output on a handful of sample (query, chunk)
        pairs for this specific model + export before deploying — not
        guessed per-score at runtime from the output's numeric range.
        A raw logit of 0.7 is a perfectly ordinary unbounded value;
        treating "falls within [0,1]" as proof of "already normalized"
        silently mistreats it, compressing/distorting scores near
        your relevance threshold in a way that won't crash anything
        and is easy to miss. Default assumes BAAI/bge-reranker-base's
        standard export emits raw logits — flip this only after
        verifying your actual export's behavior.
        """

        self._model_name = model_name
        self._raw_output_is_logit = raw_output_is_logit
        self._model: Any | None = None

        log.info(
            "Configured ONNX reranker model '%s' (raw_output_is_logit=%s).",
            model_name,
            raw_output_is_logit,
        )

    def _load(self) -> Any:
        """
        Lazily load the cross-encoder using the ONNX backend.

        PyTorch is intentionally not imported here. The RAG MCP
        runtime only requires sentence-transformers + onnxruntime.
        """
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                log.info(
                    "Loading ONNX reranker model '%s'.",
                    self._model_name,
                )

                self._model = CrossEncoder(
                    self._model_name,
                    backend="onnx",
                )

            except Exception as exc:
                log.exception(
                    "Failed to load ONNX reranker model '%s'.",
                    self._model_name,
                )

                raise RerankError(
                    message=f"Failed to load ONNX reranker model '{self._model_name}'."
                ) from exc

        return self._model

    def _normalize_score(self, value: float) -> float:
        if not self._raw_output_is_logit:
            # Verified (not guessed) that this export already emits a
            # bounded score — clamp only to protect against a value
            # slightly outside [0,1] from floating point noise.
            return max(0.0, min(1.0, value))

        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[tuple[Chunk, float]]:
        """
        Re-score candidates and return the top_k candidates sorted by
        cross-encoder relevance score.

        The original retrieval score is intentionally discarded after
        reranking.
        """

        if not candidates or top_k <= 0:
            return []

        try:
            model = self._load()
            pairs = [(query, chunk.text) for chunk, _ in candidates]

            raw_scores = await asyncio.to_thread(model.predict, pairs, convert_to_numpy=True)
            scores = [self._normalize_score(float(score)) for score in raw_scores]
        except RerankError:
            raise
        except Exception as exc:
            log.exception("Reranking failed for %d candidate(s).", len(candidates))
            raise RerankError(message="Reranking failed.") from exc

        scored = list(zip((chunk for chunk, _ in candidates), scores, strict=True))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
