from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedBlock:
    """
    A bounded piece of text extracted from a source.

    A block is intentionally small so the ingestion pipeline can process
    arbitrarily large documents without retaining the complete document
    in memory.
    """

    text: str
    source: str
    mime_type: str | None = None
    title: str | None = None
    sequence: int = 0


@dataclass(frozen=True, slots=True)
class IngestionChunk:
    """
    A bounded semantic unit produced by the ingestion chunker.

    Chunk is immutable so it can safely move between ingestion stages,
    worker threads, processes, queues, and persistence layers.
    """

    text: str
    sequence: int
    source: str
    mime_type: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentSource:
    """
    Source descriptor consumed by the document-ingestion capability.

    The source describes where a document comes from without coupling
    the ingestion contract to a particular transport or storage system.

    Examples:

        local file:
            location="/data/contracts/contract.pdf"

        remote document:
            location="https://example.com/contract.pdf"

        object storage:
            location="s3://bucket/contracts/contract.pdf"

    Concrete ingestion implementations decide how to interpret the
    location.
    """

    id: str | None
    location: str
    mime_type: str | None = None
