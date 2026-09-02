"""
Document indexing application service.

Coordinates generic document ingestion with RAG indexing.

The service is deliberately independent of the concrete ingestion mode.

Supported implementations can include:

    - offline/local ingestion
    - online ingestion
    - updated document ingestion
    - remote ingestion
    - event-driven ingestion

Flow:

    DocumentSource
        ↓
    DocumentIngestionProtocol
        ↓
    Iterator[IngestionChunk]
        ↓
    ChunkMapper
        ↓
    Iterator[RAG Chunk]
        ↓
    RAGIndexerProtocol
        ↓
    IndexedRepresentation
"""

from __future__ import annotations

from adapters.observability.logger import get_logger
from core.exceptions.rag import RAGError
from rag.chunk_mapper import ChunkMapper
from rag.ingestion.exceptions import IngestionError
from rag.ingestion.models import DocumentSource
from rag.models import IndexedRepresentation
from rag.protocols.document_ingestion import DocumentIngestionProtocol
from rag.protocols.indexer import RAGIndexerProtocol

logger = get_logger(__name__)


class DocumentIndexingService:
    """
    Application service coordinating document ingestion and RAG indexing.

    The service owns the boundary between the ingestion plane and the
    RAG indexing plane.

    Responsibilities:

        1. request document ingestion through the ingestion capability
        2. convert ingestion chunks into RAG chunks
        3. stream those chunks into the RAG indexer
        4. return indexing statistics

    Concrete ingestion implementations are deliberately not known here.
    This service depends only on capabilities/protocols and therefore
    remains independent of the concrete ingestion implementation.
    """

    def __init__(
        self,
        *,
        ingestion_service: DocumentIngestionProtocol,
        indexer: RAGIndexerProtocol,
        chunk_mapper: ChunkMapper | None = None,
    ) -> None:
        """
        Initialize the document indexing service.

        Args:
            ingestion_service:
                Generic document-ingestion capability.

            chunk_mapper:
                Conversion boundary between ingestion-domain chunks and
                RAG-domain chunks.

            indexer:
                RAG indexing orchestrator responsible for embedding
                generation and persistence.
        """

        self._ingestion_service = ingestion_service
        self._chunk_mapper = chunk_mapper or ChunkMapper()
        self._indexer = indexer

    async def index(
        self,
        *,
        source: DocumentSource,
    ) -> IndexedRepresentation:
        """
        Ingest and index one document.

        The document is processed as a stream. The complete document
        or complete chunk collection is never accumulated in memory.

        Flow:

            DocumentSource
                ↓
            DocumentIngestionProtocol.ingest()
                ↓
            ChunkMapper.map_stream()
                ↓
            RAGIndexer.index()

        Args:
            source:
                Document source descriptor containing the stable source
                identifier and source location.

        Returns:
            Statistics describing the completed indexing operation.

        Raises:
            IngestionError:
                If document ingestion fails.

            RAGError:
                If chunk conversion or RAG indexing fails.
        """

        if not isinstance(source, DocumentSource):
            raise TypeError(
                "source must be a DocumentSource.",
            )

        if not source.location.strip():
            raise ValueError(
                "source.location must not be empty.",
            )

        logger.info(
            "Starting document indexing.",
            extra={
                "source": source.location,
                "source_id": source.id,
            },
        )

        try:
            ingestion_chunks = self._ingestion_service.ingest(
                source=source,
            )

            rag_chunks = self._chunk_mapper.map_stream(
                chunks=ingestion_chunks,
                source=source,
            )

            result = await self._indexer.index(
                source_id=source.id,
                chunks=rag_chunks,
            )

        except IngestionError:
            logger.exception(
                "Document ingestion failed during indexing.",
                extra={
                    "source": source.location,
                    "source_id": source.id,
                },
            )
            raise

        except RAGError:
            logger.exception(
                "RAG indexing failed for document.",
                extra={
                    "source": source.location,
                    "source_id": source.id,
                },
            )
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected document indexing failure.",
                extra={
                    "source": source.location,
                    "source_id": source.id,
                },
            )

            raise RAGError(
                message=(f"Failed to index document " f"'{source.id}'."),
            ) from exc

        logger.info(
            "Document indexing completed.",
            extra={
                "source": source.location,
                "source_id": source.id,
                "chunk_count": result.chunk_count,
                "embedding_model": result.embedding_model,
                "embedding_dimension": result.embedding_dimension,
            },
        )

        return result
