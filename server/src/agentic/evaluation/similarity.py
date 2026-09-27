"""
Embedding-backed similarity adapter for AnswerEvaluator.

Bridges AnswerEvaluator's async SimilarityFn contract to the RAG data
plane's EmbeddingProviderProtocol (rag/embeddings.py), which is
async-only (sentence-transformers runs in a worker thread under the
hood — see SentenceTransformerEmbeddingProvider._encode_batch).

Callers must inject the SAME EmbeddingProviderProtocol instance used
elsewhere in the process (see wiring/factories/rag.py) rather than
constructing a second one — the model is expensive to load and is
meant to be a process-lifetime singleton.
"""

from __future__ import annotations

import math

from rag.protocols.embedding_provider import EmbeddingProviderProtocol


class EmbeddingSimilarity:
    """
    Async SimilarityFn implementation backed by a shared embedding provider.

    Instances are directly usable as AnswerEvaluator's ``similarity``
    argument: ``AnswerEvaluator(similarity=EmbeddingSimilarity(...), ...)``.
    Only relevance/completeness/correctness use this -- groundedness is
    judged by a separate injected FaithfulnessBackend (see answer.py).
    """

    def __init__(self, *, embedding_provider: EmbeddingProviderProtocol) -> None:
        self._embedding_provider = embedding_provider

    async def __call__(self, a: str, b: str) -> float:
        if not a.strip() or not b.strip():
            return 0.0

        vector_a, vector_b = await self._embedding_provider.embed(
            texts=[a, b],
        )

        return _cosine_similarity(vector_a, vector_b)


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """
    Cosine similarity between two vectors.

    Computed directly rather than assumed from provider-side
    normalization, since EmbeddingProviderProtocol does not guarantee
    unit-normalized output.
    """

    dot = sum(x * y for x, y in zip(vector_a, vector_b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in vector_a))
    norm_b = math.sqrt(sum(y * y for y in vector_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)
