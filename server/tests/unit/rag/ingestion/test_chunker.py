"""
Tests for title propagation through TextChunker.

ParsedBlock.title must survive into the emitted IngestionChunk,
following exactly the same "metadata of the block that started the
chunk wins" rule already implemented for source/mime_type (see
_ChunkState's docstring in chunker.py).
"""

from __future__ import annotations

from rag.ingestion.chunker import TextChunker
from rag.ingestion.models import ParsedBlock


def test_chunk_title_matches_originating_block() -> None:
    chunker = TextChunker()

    blocks = iter(
        [
            ParsedBlock(
                text="Section 1. Short title.",
                source="file",
                mime_type="application/pdf",
                title="Doc A",
                sequence=0,
            ),
        ]
    )

    chunks = list(chunker.chunk(blocks))

    assert chunks
    assert all(chunk.title == "Doc A" for chunk in chunks)


def test_chunk_title_reflects_block_that_started_the_chunk_when_spanning_blocks() -> None:
    """
    A chunk's title must reflect whichever block started it, not a
    later block that merely continues into the same chunk -- mirroring
    how source/mime_type already behave.
    """

    chunker = TextChunker()

    blocks = iter(
        [
            ParsedBlock(
                text="Section 1. Short title.",
                source="file",
                mime_type="application/pdf",
                title="Doc A",
                sequence=0,
            ),
            ParsedBlock(
                text="Section 2. Extended provisions apply.",
                source="file",
                mime_type="application/pdf",
                title="Doc B",
                sequence=1,
            ),
        ]
    )

    chunks = list(chunker.chunk(blocks))

    # Both sentences are small enough to land in the same chunk; that
    # chunk must keep the title of whichever block started it.
    assert len(chunks) == 1
    assert chunks[0].title == "Doc A"


def test_chunk_title_defaults_to_none_when_block_has_no_title() -> None:
    chunker = TextChunker()

    blocks = iter(
        [
            ParsedBlock(
                text="Plain text with no title metadata.",
                source="file",
                mime_type="text/plain",
                sequence=0,
            ),
        ]
    )

    chunks = list(chunker.chunk(blocks))

    assert chunks
    assert all(chunk.title is None for chunk in chunks)
