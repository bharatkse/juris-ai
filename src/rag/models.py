"""
RAG domain models.

These models represent the data-plane objects shared by ingestion,
indexing, retrieval, and reranking.

Ingestion-specific models such as ParsedBlock remain under
rag.ingestion.models.

The models in this module do not contain persistence or orchestration
logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Chunk:
    """
    Searchable textual unit produced by the ingestion pipeline.
    """

    id: str
    source_id: str | None
    text: str
    metadata: dict[str, str] = field(
        default_factory=dict,
    )


@dataclass(frozen=True, slots=True)
class EmbeddingRepresentation:
    """
    Embedding representation associated with a Chunk.
    """

    model_name: str
    dimension: int
    vector: list[float]


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """
    One evidence item returned by a retrieval strategy.

    This represents an individual retrieved Chunk.

    RAGResult will later represent the complete retrieval response
    returned to the agent.
    """

    chunk: Chunk
    score: float
    embeddings: list[EmbeddingRepresentation] = field(
        default_factory=list,
    )

    def with_score(
        self,
        score: float,
    ) -> RetrievalResult:
        """
        Return a new result with the supplied score.
        """

        return RetrievalResult(
            chunk=self.chunk,
            score=score,
            embeddings=self.embeddings,
        )


@dataclass(frozen=True, slots=True)
class IndexedRepresentation:
    """
    Statistics describing a completed indexing operation.
    """

    source_id: str
    chunk_count: int
    embedding_model: str
    embedding_dimension: int


@dataclass(frozen=True, slots=True)
class EmbeddingMetadata:
    """
    Metadata describing an embedding representation.
    """

    model_name: str
    dimension: int
