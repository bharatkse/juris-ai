"""
Streaming document ingestion pipeline.

Pipeline:

    Source
      ↓
    Parser
      ↓
    Security Sanitizer
      ↓
    Content Validator
      ↓
    Streaming Chunker
      ↓
    Iterator[IngestionChunk]

The pipeline processes one ParsedBlock at a time and never loads an
entire document into memory.

The pipeline instance contains configuration/dependencies only and
stores no document-specific mutable state, making it safe for concurrent
use.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Generic, TypeVar

from adapters.observability.logger import get_logger
from rag.ingestion.exceptions import IngestionError
from rag.ingestion.models import IngestionChunk, ParsedBlock
from rag.ingestion.parsers.protocol import ParserProtocol
from rag.ingestion.sanitizer import SecuritySanitizer
from rag.ingestion.text_chunker import TextChunker
from rag.ingestion.validator import ContentValidator

logger = get_logger(__name__)

SourceT = TypeVar("SourceT")


class IngestionPipeline(Generic[SourceT]):
    """
    Orchestrates the streaming preprocessing stages of document
    ingestion.

    Responsibilities:

        1. Parse the source.
        2. Sanitize each parsed block.
        3. Validate each sanitized block.
        4. Stream validated blocks into the chunker.
        5. Yield chunks immediately.

    The pipeline does not:

        - accumulate ParsedBlock objects
        - accumulate chunks
        - persist data
        - generate embeddings
        - update vector indexes
        - manage transactions
        - manage Celery/background jobs

    Those responsibilities belong to later ingestion stages.
    """

    def __init__(
        self,
        *,
        parser: ParserProtocol[SourceT],
        sanitizer: SecuritySanitizer | None = None,
        validator: ContentValidator | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        if parser is None:
            raise ValueError(
                "parser cannot be None.",
            )

        self._parser = parser
        self._sanitizer = sanitizer or SecuritySanitizer()
        self._validator = validator or ContentValidator()
        self._chunker = chunker or TextChunker()

    def ingest(
        self,
        *,
        source: SourceT,
    ) -> Iterator[IngestionChunk]:
        """
        Lazily execute the complete ingestion preprocessing pipeline.

        Parsing, sanitization, validation, and chunking occur only when
        the returned iterator is consumed.

        Args:
            source:
                Source accepted by the configured parser.

        Yields:
            IngestionChunk objects produced by the streaming chunker.

        Raises:
            IngestionError:
                If an unexpected failure occurs during ingestion.
        """

        try:
            validated_blocks = self._validated_blocks(
                source=source,
            )

            yield from self._chunker.chunk(
                validated_blocks,
            )

        except IngestionError:
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error during document ingestion.",
                extra={
                    "source": self._safe_source_repr(source),
                },
            )

            raise IngestionError(
                "Document ingestion pipeline failed.",
            ) from exc

    def _validated_blocks(
        self,
        *,
        source: SourceT,
    ) -> Iterator[ParsedBlock]:
        """
        Lazily parse, sanitize, and validate document blocks.

        Exactly one ParsedBlock is processed at a time.

        Rejected blocks are discarded immediately and therefore do not
        accumulate in memory.
        """

        try:
            for parsed_block in self._parser.parse(
                source=source,
            ):
                if not parsed_block.text:
                    logger.debug(
                        "Skipping empty parsed block.",
                        extra={
                            "sequence": parsed_block.sequence,
                        },
                    )
                    continue

                sanitized = self._sanitizer.sanitize_and_scan(
                    parsed_block.text,
                )

                if not sanitized.is_safe:
                    logger.warning(
                        "Skipping block rejected by security sanitizer.",
                        extra={
                            "sequence": parsed_block.sequence,
                            "threat_count": len(
                                sanitized.threats,
                            ),
                        },
                    )
                    continue

                validation = self._validator.validate(
                    sanitized.clean_text,
                )

                if not validation.is_valid:
                    logger.warning(
                        "Skipping block rejected by content validator.",
                        extra={
                            "sequence": parsed_block.sequence,
                            "error_count": len(
                                validation.errors,
                            ),
                        },
                    )
                    continue

                yield ParsedBlock(
                    text=sanitized.clean_text,
                    source=parsed_block.source,
                    mime_type=parsed_block.mime_type,
                    sequence=parsed_block.sequence,
                )

        except IngestionError:
            raise

        except Exception as exc:
            logger.exception(
                "Failed while validating parsed document blocks.",
                extra={
                    "source": self._safe_source_repr(source),
                },
            )

            raise IngestionError(
                "Document block validation failed.",
            ) from exc

    @staticmethod
    def _safe_source_repr(
        source: object,
    ) -> str:
        """
        Produce a bounded, non-sensitive source representation for logs.

        Avoids logging complete source contents or potentially sensitive
        document payloads.
        """

        try:
            value = str(source)

            if len(value) > 256:
                return f"{value[:256]}..."

            return value

        except Exception:
            return "<unrepresentable-source>"
