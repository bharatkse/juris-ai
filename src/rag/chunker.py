"""
Text chunker.

Splits on sentence boundaries where possible instead of raw character
counts — cutting a chunk mid-sentence (or mid-clause, common in
contract text: "...subject to Section 14.2 of th|is Agreement...")
degrades the embedding for both halves. Falls back to hard character
splitting only for pathological input (single sentence longer than
chunk_size, e.g. a run-on clause with no periods).

Abbreviation handling: a naive split on [.!?] followed by whitespace
incorrectly breaks after "v.", "Corp.", "Sec.", etc. A lookbehind
regex was the first attempt at fixing this, but Python's `re` module
requires every branch of a lookbehind alternation to be the same
fixed width — "v" (1 char) and "corp" (4 chars) in the same
alternation is invalid and raises `re.error: look-behind requires
fixed-width pattern` at compile time, which is a hard crash on
import, not a soft failure. This version checks the word preceding
each candidate boundary explicitly instead of using a lookbehind,
which works for abbreviations of any length.
"""

from __future__ import annotations

import re

_ABBREVIATIONS = (
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
)

# Matches one of the abbreviations above at the end of the preceding
# text, as a whole token (preceded by start-of-string or a
# non-alphanumeric character) — not as a substring of a longer word
# (so "Cisco" doesn't false-match "co").
_ABBREVIATION_AT_END = re.compile(
    r"(?:^|[^A-Za-z0-9])(" + "|".join(re.escape(a) for a in _ABBREVIATIONS) + r")$",
    re.IGNORECASE,
)

# Candidate sentence boundaries: sentence-ending punctuation followed
# by whitespace. No lookbehind needed here — the abbreviation check
# happens separately, in Python, against the text before the match.
_BOUNDARY = re.compile(r"[.!?]\s+")


def split_sentences(text: str) -> list[str]:
    """
    Naive sentence splitter. Good enough for chunking purposes — it
    doesn't need to be linguistically perfect, just better than a
    fixed character cut, and it must not split after a known
    abbreviation ("Corp.", "Sec. 14.2", "v.", "e.g.").
    """

    text = text.strip()

    if not text:
        return []

    sentences: list[str] = []
    last_end = 0

    for match in _BOUNDARY.finditer(text):
        boundary_start = match.start()
        preceding_text = text[:boundary_start]

        if _ABBREVIATION_AT_END.search(preceding_text):
            # Don't split here — "Corp." / "v." / "Sec." isn't a
            # sentence end, keep scanning for the next boundary.
            continue

        sentences.append(text[last_end : match.end()].strip())
        last_end = match.end()

    tail = text[last_end:].strip()

    if tail:
        sentences.append(tail)

    return [s for s in sentences if s]


def chunk_text(
    *,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """
    Greedily pack sentences into chunks up to chunk_size chars with
    overlap. Safely handles boundary overflow without dropping text.
    """

    if chunk_size <= chunk_overlap or chunk_overlap < 0:
        raise ValueError(
            f"Invalid configuration: chunk_size ({chunk_size}) must be strictly "
            f"greater than chunk_overlap ({chunk_overlap}), and chunk_overlap >= 0."
        )

    sentences = split_sentences(text)

    if not sentences:
        return []

    step = chunk_size - chunk_overlap
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            overlap_prefix = current[-chunk_overlap:].strip() if chunk_overlap else ""
            candidate = f"{overlap_prefix} {sentence}".strip() if overlap_prefix else sentence

            if len(candidate) <= chunk_size:
                current = candidate
                continue

            current = ""
            sentence_to_split = candidate
        else:
            sentence_to_split = sentence

        # Hard-split long sentences or long overlap+sentence combinations
        for start in range(0, len(sentence_to_split), step):
            piece = sentence_to_split[start : start + chunk_size]

            if len(piece) == chunk_size or (start + step >= len(sentence_to_split)):
                chunks.append(piece)
            else:
                current = piece

    if current and (not chunks or chunks[-1] != current):
        chunks.append(current)

    return chunks
