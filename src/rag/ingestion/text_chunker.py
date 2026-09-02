"""
Streaming sentence-aware text chunker.

Consumes ParsedBlock objects incrementally and produces immutable Chunk
objects without accumulating the complete document in memory.

The chunker maintains only bounded document state:

    - an incomplete sentence carry
    - the current output chunk
    - small overlap state

No document-sized collection is created.

The TextChunker instance itself contains configuration only and stores
no document-specific mutable state, making the instance safe to reuse
concurrently.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from adapters.observability.logger import get_logger
from rag.ingestion.exceptions import ChunkingError
from rag.ingestion.models import IngestionChunk, ParsedBlock

logger = get_logger(__name__)


_ABBREVIATIONS = frozenset(
    {
        "v",
        "vs",
        "sec",
        "art",
        "no",
        "corp",
        "inc",
        "ltd",
        "llc",
        "co",
        "e.g",
        "i.e",
        "etc",
        "fig",
        "dr",
        "mr",
        "mrs",
        "ms",
        "jr",
        "sr",
    }
)


_SENTENCE_BOUNDARY = re.compile(
    r"[.!?](?=\s+|$)",
)


@dataclass(slots=True)
class _ChunkState:
    """
    Document-local mutable chunking state.

    This object is created inside chunk() and is never stored on the
    TextChunker instance.

    Therefore concurrent chunk() calls have completely independent state.
    """

    current_chunk: str = ""
    chunk_sequence: int = 0


class TextChunker:
    """
    Streaming sentence-aware text chunker.

    Thread-safety:
        The instance contains configuration only.
        No document-specific mutable state is stored on the instance.

    Memory behavior:
        - Does not load the complete document.
        - Does not accumulate emitted chunks.
        - Emits chunks immediately.
        - Maintains only bounded sentence carry and current chunk state.
    """

    def __init__(
        self,
        *,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
        max_sentence_carry: int | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater than zero.",
            )

        if chunk_overlap < 0:
            raise ValueError(
                "chunk_overlap cannot be negative.",
            )

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size.",
            )

        if max_sentence_carry is not None:
            if max_sentence_carry <= 0:
                raise ValueError(
                    "max_sentence_carry must be greater than zero.",
                )

            if max_sentence_carry < chunk_size:
                raise ValueError(
                    "max_sentence_carry must be greater than or equal " "to chunk_size.",
                )

        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._max_sentence_carry = (
            max_sentence_carry if max_sentence_carry is not None else chunk_size * 2
        )

    def chunk(
        self,
        blocks: Iterator[ParsedBlock],
    ) -> Iterator[IngestionChunk]:
        """
        Incrementally convert ParsedBlock objects into Chunk objects.

        A sentence can span multiple parser blocks. An incomplete
        sentence is retained temporarily in a bounded carry buffer.

        All mutable state is local to this generator invocation.
        """

        state = _ChunkState()

        sentence_carry = ""

        carry_source: str | None = None
        carry_mime_type: str | None = None

        try:
            for block in blocks:
                if not block.text:
                    continue

                text = block.text.strip()

                if not text:
                    continue

                # ---------------------------------------------------------
                # Combine previous incomplete sentence with current block.
                # ---------------------------------------------------------

                if sentence_carry:
                    sentence_carry = f"{sentence_carry} {text}"
                else:
                    sentence_carry = text

                carry_source = block.source
                carry_mime_type = block.mime_type

                (
                    complete_sentences,
                    sentence_carry,
                ) = self._extract_complete_sentences(
                    sentence_carry,
                )

                # ---------------------------------------------------------
                # Process completed sentences.
                # ---------------------------------------------------------

                for sentence in complete_sentences:
                    if not sentence:
                        continue

                    yield from self._append_sentence(
                        sentence=sentence,
                        state=state,
                        source=carry_source or block.source,
                        mime_type=(carry_mime_type or block.mime_type),
                    )

                # ---------------------------------------------------------
                # Protect against pathological sentences with no boundary.
                # ---------------------------------------------------------

                if len(sentence_carry) > self._max_sentence_carry:
                    logger.warning(
                        "Sentence carry exceeded configured limit; "
                        "forcing bounded split. "
                        "carry_length=%d max_sentence_carry=%d",
                        len(sentence_carry),
                        self._max_sentence_carry,
                    )

                    if state.current_chunk:
                        yield IngestionChunk(
                            text=state.current_chunk,
                            sequence=state.chunk_sequence,
                            source=carry_source or block.source,
                            mime_type=(carry_mime_type or block.mime_type),
                        )

                        state.chunk_sequence += 1
                        state.current_chunk = ""

                    for piece in self._split_long_text(
                        sentence_carry,
                    ):
                        yield IngestionChunk(
                            text=piece,
                            sequence=state.chunk_sequence,
                            source=carry_source or block.source,
                            mime_type=(carry_mime_type or block.mime_type),
                        )

                        state.chunk_sequence += 1

                    sentence_carry = ""

            # -------------------------------------------------------------
            # Flush final incomplete sentence.
            # -------------------------------------------------------------

            if sentence_carry:
                yield from self._append_sentence(
                    sentence=sentence_carry,
                    state=state,
                    source=carry_source or "unknown",
                    mime_type=carry_mime_type,
                )

            # -------------------------------------------------------------
            # Flush final current chunk.
            # -------------------------------------------------------------

            if state.current_chunk:
                yield IngestionChunk(
                    text=state.current_chunk,
                    sequence=state.chunk_sequence,
                    source=carry_source or "unknown",
                    mime_type=carry_mime_type,
                )

        except ChunkingError:
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error during text chunking.",
            )

            raise ChunkingError(
                "Text chunking failed.",
            ) from exc

    def _append_sentence(
        self,
        *,
        sentence: str,
        state: _ChunkState,
        source: str,
        mime_type: str | None,
    ) -> Iterator[IngestionChunk]:
        """
        Add a sentence to the current chunk.

        Chunks are yielded immediately.

        No list of emitted chunks is created.

        State mutation is limited to the document-local _ChunkState
        supplied by chunk().
        """

        if not sentence:
            return

        # -------------------------------------------------------------
        # Case 1: sentence itself exceeds chunk_size.
        # -------------------------------------------------------------

        if len(sentence) > self._chunk_size:
            if state.current_chunk:
                yield IngestionChunk(
                    text=state.current_chunk,
                    sequence=state.chunk_sequence,
                    source=source,
                    mime_type=mime_type,
                )

                state.chunk_sequence += 1
                state.current_chunk = ""

            for piece in self._split_long_text(sentence):
                yield IngestionChunk(
                    text=piece,
                    sequence=state.chunk_sequence,
                    source=source,
                    mime_type=mime_type,
                )

                state.chunk_sequence += 1

            return

        # -------------------------------------------------------------
        # Case 2: sentence fits into current chunk.
        # -------------------------------------------------------------

        candidate = f"{state.current_chunk} {sentence}".strip() if state.current_chunk else sentence

        if len(candidate) <= self._chunk_size:
            state.current_chunk = candidate
            return

        # -------------------------------------------------------------
        # Case 3: current chunk is full.
        # Emit current chunk first.
        # -------------------------------------------------------------

        if state.current_chunk:
            yield IngestionChunk(
                text=state.current_chunk,
                sequence=state.chunk_sequence,
                source=source,
                mime_type=mime_type,
            )

            state.chunk_sequence += 1

        previous_chunk = state.current_chunk

        # -------------------------------------------------------------
        # Try adding sentence with configured overlap.
        # -------------------------------------------------------------

        overlap = self._get_overlap(
            previous_chunk,
        )

        candidate = f"{overlap} {sentence}".strip() if overlap else sentence

        if len(candidate) <= self._chunk_size:
            state.current_chunk = candidate
            return

        # -------------------------------------------------------------
        # Case 4: sentence cannot fit even with overlap.
        # Split it directly.
        # -------------------------------------------------------------

        state.current_chunk = ""

        for piece in self._split_long_text(sentence):
            yield IngestionChunk(
                text=piece,
                sequence=state.chunk_sequence,
                source=source,
                mime_type=mime_type,
            )

            state.chunk_sequence += 1

    def _extract_complete_sentences(
        self,
        text: str,
    ) -> tuple[list[str], str]:
        """
        Extract complete sentences from text.

        The incomplete tail is returned separately so it can be retained
        across ParsedBlock boundaries.
        """

        normalized = text.strip()

        if not normalized:
            return [], ""

        sentences: list[str] = []
        sentence_start = 0

        for match in _SENTENCE_BOUNDARY.finditer(
            normalized,
        ):
            preceding = normalized[sentence_start : match.start()]

            if self._is_abbreviation(
                preceding,
            ):
                continue

            sentence_end = match.end()

            sentence = normalized[sentence_start:sentence_end].strip()

            if sentence:
                sentences.append(sentence)

            sentence_start = sentence_end

        tail = normalized[sentence_start:].strip()

        return sentences, tail

    @staticmethod
    def _is_abbreviation(
        preceding_text: str,
    ) -> bool:
        """
        Determine whether punctuation belongs to a known abbreviation.
        """

        match = re.search(
            r"([A-Za-z](?:\.[A-Za-z])?|[A-Za-z]+)$",
            preceding_text,
        )

        if not match:
            return False

        return match.group(1).lower() in _ABBREVIATIONS

    def _split_long_text(
        self,
        text: str,
    ) -> Iterator[str]:
        """
        Hard-split text exceeding chunk_size.

        Uses bounded overlap and yields pieces immediately.
        """

        if len(text) <= self._chunk_size:
            yield text
            return

        step = self._chunk_size - self._chunk_overlap

        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(
                start + self._chunk_size,
                text_length,
            )

            piece = text[start:end].strip()

            if piece:
                yield piece

            if end >= text_length:
                break

            start += step

    def _get_overlap(
        self,
        text: str,
    ) -> str:
        """
        Return bounded word-aware overlap from the previous chunk.
        """

        if self._chunk_overlap <= 0 or not text:
            return ""

        overlap = text[-self._chunk_overlap :]

        first_space = overlap.find(" ")

        if first_space > 0:
            overlap = overlap[first_space + 1 :]

        return overlap.strip()
