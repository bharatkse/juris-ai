"""
Streaming sentence-aware text chunker.

Consumes ParsedBlock objects incrementally and produces immutable Chunk
objects without accumulating the complete document in memory.

The chunker maintains only bounded document state:

    - an incomplete sentence carry
    - the current output chunk (and the source/mime_type/title it was built from)
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
from rag.ingestion.chunking_profile import ChunkingProfileSelector
from rag.ingestion.exceptions import ChunkingError
from rag.ingestion.models import ChunkingProfile, IngestionChunk, ParsedBlock

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
        "u.s",
        "s.c",
    }
)


_SENTENCE_BOUNDARY = re.compile(
    r"[.!?](?=\s+|$)",
)


_FOOTNOTE_LINE_START = re.compile(r"^[ \t]*\d+\.[ \t]+")

_FOOTNOTE_VOCABULARY = re.compile(
    r"\b(?:Subs|Ins|Omitted|omitted|Cl|Sch|Notifn|ibid|AIR)\.?\b|w\.e\.f\.",
)

_FOOTNOTE_CLOSING = re.compile(
    r"\(w\.e\.f\.[^)]*\)\.|AIR\s+\d{4}[^\n]*\.$",
)

# "20. [Controller to act as repository.] Omitted by the Information
# Technology (Amendment) Act, 2008 ... (w.e.f. ...)." is the real body
# text of an omitted *section* (a bracketed title right after the
# number), not a footnote -- even though it contains "Omitted" and
# "w.e.f." just like a real footnote does. Indian legislative drafting
# uses this exact phrasing for both, so the bracket-right-after-the-
# number is the only reliable signal telling them apart.
_OMITTED_SECTION_HEADER = re.compile(r"^[ \t]*\d+[A-Za-z]?\.[ \t]*\[")


_LEGAL_PROVISION_BOUNDARY = re.compile(
    r"""
    ^
    [ \t]*
    (?:
        section\s+\d+[A-Za-z]?
        |
        \d+[A-Za-z]?
        |
        article\s+\d+[A-Za-z]?
        |
        schedule\s+\d+[A-Za-z]?
    )
    (?=
        \s+
        |
        [.\-—:]
        |
        \(
    )
    """,
    re.MULTILINE | re.VERBOSE,
)


@dataclass(slots=True)
class _ChunkState:
    """
    Document-local mutable chunking state.

    This object is created inside chunk() and is never stored on the
    TextChunker instance.

    Therefore concurrent chunk() calls have completely independent state.

    current_chunk_source / current_chunk_mime_type / current_chunk_title
    describe the metadata that was in effect when the *current* chunk
    was started (i.e. the metadata of the first segment that went into
    it), not the metadata of whatever segment happens to be arriving
    when the chunk is later emitted. Tracking this separately is what
    keeps emitted chunk metadata correct when a chunk's content spans
    multiple ParsedBlocks (e.g. multiple PDF pages).
    """

    current_chunk: str = ""
    current_chunk_source: str | None = None
    current_chunk_mime_type: str | None = None
    current_chunk_title: str | None = None
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
        profile: ChunkingProfile | None = None,
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

        # None means "derive dynamically from whichever profile is active
        # for this chunk() call"; an explicit value is treated as a hard
        # user override and always wins (see _resolve_max_sentence_carry).
        self._max_sentence_carry_override = max_sentence_carry

        self._profile = profile or ChunkingProfile(
            target_size=chunk_size,
            max_size=chunk_size,
            overlap=chunk_overlap,
            preserve_structure=True,
        )

    def _resolve_max_sentence_carry(self, active_profile: ChunkingProfile) -> int:
        """
        Derive the pathological-carry limit from whichever profile is
        actually active for this document, rather than from the
        constructor's chunk_size. This keeps the limit consistent when a
        profile_selector swaps in e.g. the legal profile mid-stream.
        """

        if self._max_sentence_carry_override is not None:
            return self._max_sentence_carry_override

        return active_profile.max_size * 2

    def chunk(
        self,
        blocks: Iterator[ParsedBlock],
        *,
        profile_selector: ChunkingProfileSelector | None = None,
    ) -> Iterator[IngestionChunk]:
        """
        Incrementally convert ParsedBlock objects into IngestionChunk objects.

        A sentence can span multiple parser blocks. An incomplete
        sentence is retained temporarily in a bounded carry buffer.

        The active ChunkingProfile is document-local and is never stored
        back on the TextChunker instance.
        """

        state = _ChunkState()

        sentence_carry = ""

        carry_source: str | None = None
        carry_mime_type: str | None = None
        carry_title: str | None = None

        active_profile = self._profile
        profile_selected = False
        max_sentence_carry = self._resolve_max_sentence_carry(active_profile)
        footnote_carry = False

        try:
            for block in blocks:
                if not block.text:
                    continue

                text = block.text.strip()

                if not text:
                    continue

                # ---------------------------------------------------------
                # Select the profile once for this chunk() invocation.
                # ---------------------------------------------------------

                if profile_selector is not None and not profile_selected:
                    active_profile = profile_selector.select(block)
                    profile_selected = True
                    max_sentence_carry = self._resolve_max_sentence_carry(active_profile)

                # ---------------------------------------------------------
                # Strip amendment-footnote lines (a PDF-extraction
                # artifact for gazette-style legal text, where footnote
                # markers get linearised in-line with the body). This is
                # a targeted heuristic keyed to the standard IndiaCode
                # amendment-note vocabulary (Subs., Ins., Cl., Sch.,
                # etc.), not a general-purpose footnote detector -- it
                # will not catch every footnote convention, and true
                # layout-aware footnote removal belongs in the PDF
                # parsing stage, not here.
                # ---------------------------------------------------------

                if active_profile.preserve_structure:
                    text, footnote_carry = self._strip_amendment_footnotes(
                        text,
                        carry_in_footnote=footnote_carry,
                    )

                    if not text:
                        continue

                # ---------------------------------------------------------
                # Combine previous incomplete sentence with current block.
                #
                # Preserve a line boundary so legal provision markers
                # remain detectable across parser blocks.
                # ---------------------------------------------------------

                if sentence_carry:
                    sentence_carry = f"{sentence_carry}\n{text}"
                else:
                    sentence_carry = text

                # Preserve metadata belonging to the beginning of the
                # carried logical unit.
                if carry_source is None:
                    carry_source = block.source

                if carry_mime_type is None:
                    carry_mime_type = block.mime_type

                if carry_title is None:
                    carry_title = block.title

                (
                    complete_segments,
                    sentence_carry,
                ) = self._extract_complete_segments(
                    sentence_carry,
                    profile=active_profile,
                )

                # ---------------------------------------------------------
                # Process completed sentences / legal provisions.
                # ---------------------------------------------------------

                for segment in complete_segments:
                    if not segment:
                        continue

                    yield from self._append_sentence(
                        sentence=segment,
                        state=state,
                        source=carry_source or block.source,
                        mime_type=(carry_mime_type or block.mime_type),
                        title=(carry_title or block.title),
                        profile=active_profile,
                    )

                # The carry was completely consumed.
                if not sentence_carry:
                    carry_source = None
                    carry_mime_type = None
                    carry_title = None

                # ---------------------------------------------------------
                # Protect against pathological sentences with no boundary.
                # ---------------------------------------------------------

                if len(sentence_carry) > max_sentence_carry:
                    logger.warning(
                        "Sentence carry exceeded configured limit; "
                        "forcing bounded split. "
                        "carry_length=%d max_sentence_carry=%d",
                        len(sentence_carry),
                        max_sentence_carry,
                    )

                    if state.current_chunk:
                        yield IngestionChunk(
                            text=state.current_chunk,
                            sequence=state.chunk_sequence,
                            source=state.current_chunk_source or "unknown",
                            mime_type=state.current_chunk_mime_type,
                            title=state.current_chunk_title,
                        )

                        state.chunk_sequence += 1
                        state.current_chunk = ""
                        state.current_chunk_source = None
                        state.current_chunk_mime_type = None
                        state.current_chunk_title = None

                    for piece in self._split_long_text(
                        sentence_carry,
                        profile=active_profile,
                    ):
                        yield IngestionChunk(
                            text=piece,
                            sequence=state.chunk_sequence,
                            source=carry_source or block.source,
                            mime_type=(carry_mime_type or block.mime_type),
                            title=(carry_title or block.title),
                        )

                        state.chunk_sequence += 1

                    sentence_carry = ""
                    carry_source = None
                    carry_mime_type = None
                    carry_title = None

            # -------------------------------------------------------------
            # Flush final incomplete sentence / legal provision.
            #
            # Do not re-run _extract_complete_segments(). At end-of-input,
            # the remaining carry is the final logical unit.
            # -------------------------------------------------------------

            if sentence_carry:
                yield from self._append_sentence(
                    sentence=sentence_carry,
                    state=state,
                    source=carry_source or "unknown",
                    mime_type=carry_mime_type,
                    title=carry_title,
                    profile=active_profile,
                )

            # -------------------------------------------------------------
            # Flush final current chunk.
            # -------------------------------------------------------------

            if state.current_chunk:
                yield IngestionChunk(
                    text=state.current_chunk,
                    sequence=state.chunk_sequence,
                    source=state.current_chunk_source or "unknown",
                    mime_type=state.current_chunk_mime_type,
                    title=state.current_chunk_title,
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
        title: str | None,
        profile: ChunkingProfile,
    ) -> Iterator[IngestionChunk]:
        """
        Add a sentence or logical legal segment to the current chunk.

        Chunks are yielded immediately.

        No list of emitted chunks is created.

        State mutation is limited to the document-local _ChunkState
        supplied by chunk(). Emitted chunk metadata always reflects the
        source/mime_type/title recorded when the *emitted* chunk was
        started, never the metadata of the segment that happens to be
        arriving right now.
        """

        if not sentence:
            return

        # -------------------------------------------------------------
        # Case 1: logical unit exceeds maximum configured size.
        #
        # target_size = preferred size
        # max_size    = maximum semantic unit size
        # -------------------------------------------------------------

        if len(sentence) > profile.max_size:
            if state.current_chunk:
                yield IngestionChunk(
                    text=state.current_chunk,
                    sequence=state.chunk_sequence,
                    source=state.current_chunk_source or source,
                    mime_type=state.current_chunk_mime_type or mime_type,
                    title=state.current_chunk_title or title,
                )

                state.chunk_sequence += 1
                state.current_chunk = ""
                state.current_chunk_source = None
                state.current_chunk_mime_type = None
                state.current_chunk_title = None

            for piece in self._split_long_text(
                sentence,
                profile=profile,
            ):
                yield IngestionChunk(
                    text=piece,
                    sequence=state.chunk_sequence,
                    source=source,
                    mime_type=mime_type,
                    title=title,
                )

                state.chunk_sequence += 1

            return

        # -------------------------------------------------------------
        # Case 2: sentence / provision fits into current chunk.
        # -------------------------------------------------------------

        starting_new_chunk = not state.current_chunk

        candidate = (
            f"{state.current_chunk}\n{sentence}".strip() if state.current_chunk else sentence
        )

        if len(candidate) <= profile.max_size:
            state.current_chunk = candidate

            if starting_new_chunk:
                state.current_chunk_source = source
                state.current_chunk_mime_type = mime_type
                state.current_chunk_title = title

            return

        # -------------------------------------------------------------
        # Case 3: current chunk is full.
        # Emit current chunk first, using the metadata it was started
        # with (not the metadata of the incoming sentence).
        # -------------------------------------------------------------

        if state.current_chunk:
            yield IngestionChunk(
                text=state.current_chunk,
                sequence=state.chunk_sequence,
                source=state.current_chunk_source or source,
                mime_type=state.current_chunk_mime_type or mime_type,
                title=state.current_chunk_title or title,
            )

            state.chunk_sequence += 1

        previous_chunk = state.current_chunk

        # -------------------------------------------------------------
        # Try adding sentence with configured overlap.
        #
        # The overlap text is drawn from the just-emitted previous
        # chunk, but the new chunk being built is "owned" by the
        # incoming sentence going forward, so its metadata becomes the
        # incoming segment's source/mime_type.
        # -------------------------------------------------------------

        overlap = self._get_overlap(
            previous_chunk,
            overlap_size=profile.overlap,
        )

        candidate = f"{overlap}\n{sentence}".strip() if overlap else sentence

        if len(candidate) <= profile.max_size:
            state.current_chunk = candidate
            state.current_chunk_source = source
            state.current_chunk_mime_type = mime_type
            state.current_chunk_title = title
            return

        # -------------------------------------------------------------
        # Case 4: sentence / provision cannot fit even with overlap.
        # Split it directly.
        # -------------------------------------------------------------

        state.current_chunk = ""
        state.current_chunk_source = None
        state.current_chunk_mime_type = None
        state.current_chunk_title = None

        for piece in self._split_long_text(
            sentence,
            profile=profile,
        ):
            yield IngestionChunk(
                text=piece,
                sequence=state.chunk_sequence,
                source=source,
                mime_type=mime_type,
                title=title,
            )

            state.chunk_sequence += 1

    def _extract_complete_segments(
        self,
        text: str,
        *,
        profile: ChunkingProfile,
    ) -> tuple[list[str], str]:
        """
        Extract complete semantic segments and retain incomplete carry.

        For legal text, the final detected provision is only carried as
        "incomplete" when its own content lacks a sentence-terminal
        boundary. The mere absence of a *following* provision boundary
        in the current parser block is not, by itself, evidence that the
        final provision is incomplete -- a provision can legitimately end
        cleanly at the end of a block.
        """

        text = text.strip()

        if not text:
            return [], ""

        if not profile.preserve_structure:
            return self._extract_complete_sentences(text)

        matches = [
            match
            for match in _LEGAL_PROVISION_BOUNDARY.finditer(text)
            if not self._is_bare_page_number(text, match)
        ]

        if not matches:
            return self._extract_complete_sentences(text)

        segments: list[str] = []

        # Text before the first legal provision.
        prefix = text[: matches[0].start()].strip()

        if prefix:
            prefix_segments, prefix_carry = self._extract_complete_sentences(prefix)

            if prefix_segments:
                segments.extend(prefix_segments)

            if prefix_carry:
                segments.append(prefix_carry)

        # Legal provisions.
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)

            provision = text[start:end].strip()

            if not provision:
                continue

            if index + 1 < len(matches):
                segments.append(provision)
                continue

            # Final provision in this block: decide complete vs
            # incomplete from its own trailing content, not from the
            # absence of a following boundary.
            if self._ends_with_sentence_boundary(provision):
                segments.append(provision)
                return segments, ""

            sub_segments, sub_carry = self._extract_complete_sentences(provision)
            segments.extend(sub_segments)

            return segments, sub_carry

        return segments, ""

    @staticmethod
    def _ends_with_sentence_boundary(text: str) -> bool:
        """Whether text ends on a recognised sentence-terminal boundary."""

        return bool(text) and text[-1] in ".!?"

    @staticmethod
    def _strip_amendment_footnotes(
        text: str,
        *,
        carry_in_footnote: bool = False,
    ) -> tuple[str, bool]:
        """
        Remove IndiaCode-style amendment footnote lines from a block of
        text before it enters the chunking pipeline.

        These lines (e.g. "1. Subs. by Act 10 of 2009, s. 2, ... (w.e.f.
        27-10-2009)." ) are printed at the bottom of the source page and
        get linearised into the middle of the page's extracted text,
        directly between whatever body clauses happen to straddle that
        page break. Left in place, they get spliced into the operative
        provision text.

        A footnote line is recognised by two independent signals: it
        starts like a numbered reference ("<digits>. ") *and* it carries
        one of the standard legislative-amendment vocabulary words
        (Subs., Ins., Omitted, Cl., Sch., Notifn., ibid., AIR, w.e.f.)
        somewhere on the line -- not necessarily immediately after the
        number, since real phrasing varies ("Certain words omitted by
        s. 16, ibid. ...", "The first proviso omitted by s. 17 ...").

        Footnotes commonly wrap onto a second physical line once the
        PDF text is flattened. Once inside a footnote, subsequent lines
        are treated as a continuation of it until a recognised closing
        pattern, a blank separator line, or the start of a genuine
        legal provision is seen -- whichever comes first -- so this
        can't run away and eat real body text.

        A footnote can itself wrap across a page/block boundary, so
        `carry_in_footnote` lets the caller thread "we were still
        inside a footnote at the end of the previous block" into this
        call, and the returned bool reports whether that's still true
        at the end of this block.
        """

        lines = text.split("\n")
        kept: list[str] = []
        in_footnote = carry_in_footnote

        for line in lines:
            if not in_footnote:
                if _FOOTNOTE_LINE_START.match(line) and _FOOTNOTE_VOCABULARY.search(line):
                    in_footnote = not _FOOTNOTE_CLOSING.search(line)
                    continue

                kept.append(line)
                continue

            stripped = line.strip()

            if not stripped:
                in_footnote = False
                continue

            if _LEGAL_PROVISION_BOUNDARY.match(line):
                in_footnote = False
                kept.append(line)
                continue

            if _FOOTNOTE_CLOSING.search(line):
                in_footnote = False

            # Still (or just finished) consuming the wrapped footnote
            # continuation -- drop it either way.

        return "\n".join(kept).strip(), in_footnote

    @staticmethod
    def _is_bare_page_number(text: str, match: re.Match[str]) -> bool:
        """
        Whether a provision-boundary match is actually just a standalone
        page number (a PDF-extraction artifact), not a real section,
        article, or schedule header.

        Real headers always carry a title on the same line as the
        number (e.g. "43. Penalty and compensation for damage..."). A
        bare page number has nothing but whitespace after it until the
        next line. This does not attempt to distinguish real provisions
        from footnote markers (e.g. "1. Section 66A has been struck
        down...") -- that ambiguity is not resolvable from flattened
        page text alone and should be handled by a layout-aware PDF
        parser upstream, not guessed at here.
        """

        line_end = text.find("\n", match.end())

        if line_end == -1:
            line_end = len(text)

        remainder = text[match.end() : line_end].strip()

        return not any(ch.isalpha() for ch in remainder)

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

            if self._is_abbreviation(preceding):
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

        Handles both single tokens ("Inc", "Dr") and dotted abbreviation
        chains ("U.S", "S.C") ending immediately before the boundary.
        """

        match = re.search(
            r"([A-Za-z]+(?:\.[A-Za-z]+)*)$",
            preceding_text,
        )

        if not match:
            return False

        return match.group(1).lower() in _ABBREVIATIONS

    def _split_long_text(
        self,
        text: str,
        *,
        profile: ChunkingProfile,
    ) -> Iterator[str]:
        """
        Hard-split text exceeding the configured maximum size.

        Both the split point and the start of the next window are
        aligned to whitespace where possible, so pieces don't sever
        words (e.g. "liabili|ty") at either end.
        """

        if len(text) <= profile.max_size:
            yield text
            return

        text_length = len(text)
        start = 0

        while start < text_length:
            end = min(start + profile.max_size, text_length)

            if end < text_length:
                boundary = text.rfind(" ", start, end)

                if boundary > start:
                    end = boundary

            piece = text[start:end].strip()

            if piece:
                yield piece

            if end >= text_length:
                break

            next_start = max(end - profile.overlap, start + 1)

            # Align the next window's start to a word boundary too,
            # rather than resuming mid-word.
            if next_start < text_length and text[next_start - 1] not in (" ", "\n", "\t"):
                space = text.find(" ", next_start)

                if space != -1:
                    next_start = space + 1

            start = next_start

    def _get_overlap(
        self,
        text: str,
        overlap_size: int,
    ) -> str:
        """
        Return a bounded, word-safe overlap from the end of text.

        Rather than always discarding the first word after the cut
        point (which can drop a meaningful legal token such as
        "Section" even when the cut already landed on a clean word
        boundary), this only advances past a boundary when the cut
        actually falls inside a word.
        """

        if not text or overlap_size <= 0:
            return ""

        if len(text) <= overlap_size:
            return text

        cut = len(text) - overlap_size

        if text[cut - 1] not in (" ", "\n", "\t"):
            next_space = text.find(" ", cut)

            if next_space != -1:
                cut = next_space + 1

        return text[cut:].strip()
