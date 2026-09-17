"""
Tests for FileParser's PDF title resolution.

The project has no PDF-authoring dependency (no reportlab/fpdf), so
fixture PDFs are hand-built using only pypdf -- PdfWriter for the
container plus pypdf.generic primitives for a minimal font resource
and content stream. This produces real, extractable text (not just a
blank page), which is what a PDF with no /Title metadata still needs
in order to exercise the filename-fallback branch.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from rag.ingestion.parsers.file import FileParser


def _write_pdf(path: Path, *, text: str, title: str | None) -> None:
    """
    Build a minimal single-page PDF with real extractable text and,
    optionally, an embedded /Title.
    """

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)

    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    font_ref = writer._add_object(font)

    fonts = DictionaryObject()
    fonts[NameObject("/F1")] = font_ref

    resources = DictionaryObject()
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources

    content = DecodedStreamObject()
    content.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(content)

    if title is not None:
        writer.add_metadata({"/Title": title})

    with path.open("wb") as file_handle:
        writer.write(file_handle)


def test_parse_pdf_prefers_embedded_title(tmp_path: Path) -> None:
    """
    When a PDF has embedded /Title metadata, that title -- not the
    filename -- must be used.
    """

    path = tmp_path / "irrelevant_filename.pdf"
    _write_pdf(
        path,
        text="Section 1. Short title.",
        title="The Real Act Title",
    )

    blocks = list(FileParser().parse(source=path))

    assert blocks, "Expected at least one parsed block."
    assert all(block.title == "The Real Act Title" for block in blocks)


def test_parse_pdf_falls_back_to_filename_when_no_title(tmp_path: Path) -> None:
    """
    Most of the current legal corpus has no /Title metadata at all --
    this is the common case in practice, not just a defensive edge
    case (see test_ingestion.py's smoke-test comment for confirmation
    against the real corpus). The filename (without extension) must
    be used instead.
    """

    path = tmp_path / "reservation-1985.pdf"
    _write_pdf(
        path,
        text="Section 1. Short title.",
        title=None,
    )

    blocks = list(FileParser().parse(source=path))

    assert blocks, "Expected at least one parsed block."
    assert all(block.title == "reservation-1985" for block in blocks)
