"""
Tests for the shared evidence-matching normalization helper
(rag/evaluation/metrics/text_matching.py).
"""

from __future__ import annotations

from rag.evaluation.metrics.text_matching import evidence_in_text, normalize_for_matching


def test_normalize_collapses_newline_to_space() -> None:
    text = "the signature creation data are, within the context in which they are\nused, linked"

    assert "are used" in normalize_for_matching(text)


def test_normalize_strips_whitespace_before_punctuation() -> None:
    text = "logical, arithmetical , or memory function resources"

    assert "arithmetical, or" in normalize_for_matching(text)


def test_normalize_collapses_multiple_spaces() -> None:
    text = "computer   resource"

    assert normalize_for_matching(text) == "computer resource"


def test_normalize_is_case_insensitive() -> None:
    assert normalize_for_matching("ELECTRONIC Signature") == "electronic signature"


def test_evidence_in_text_matches_across_pdf_line_wrap() -> None:
    evidence = "the signature creation data or the authentication data are, within the context in which they are used, linked to the signatory"
    chunk_text = (
        "(a) the signature creation data or the authentication data are, within the context in which they are\n"
        "used, linked to the signatory or, as the case may be, the authenticator and to no other person;"
    )

    assert evidence_in_text(evidence, chunk_text)


def test_evidence_in_text_matches_stray_space_before_comma() -> None:
    evidence = "gaining entry into, instructing or communicating with the logical, arithmetical, or memory function resources of a computer"
    chunk_text = (
        "(a) ―access― with its grammatical variations and cognate expressions means gaining entry into,\n"
        "instructing or communicating with the logical, arithmetical , or memory function resources of a\n"
        "computer, computer system or computer network;"
    )

    assert evidence_in_text(evidence, chunk_text)


def test_evidence_in_text_still_fails_on_genuine_mismatch() -> None:
    # A newline is intentionally NOT a mismatch because whitespace
    # normalization is supposed to make line-wrapped text match.
    # Use a genuine lexical mismatch instead.
    evidence = "the dispatch of an electronic record occurs when it enters a computer resource"
    chunk_text = "the dispatch of an electronic record occurs when it enters a computer system"

    assert not evidence_in_text(evidence, chunk_text)


def test_evidence_in_text_does_not_strip_inline_citation_brackets() -> None:
    # Known, deliberately-unfixed gap: inline amendment brackets like
    # "1[...]" still break a match.
    evidence = "authenticated by means of electronic signature"
    chunk_text = (
        "such information or matter is authenticated by means of 1[electronic\nsignature] affixed"
    )

    assert not evidence_in_text(evidence, chunk_text)
