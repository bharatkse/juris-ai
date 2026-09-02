from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from core.utils.resource_context_manager import ResourceContextManager
from rag.ingestion.exceptions import (
    FileSourceError,
    IngestionError,
)
from rag.ingestion.models import ParsedBlock
from rag.ingestion.parsers.protocol import ParserProtocol
from rag.ingestion.readers.file_reader import FileReader

logger = logging.getLogger(__name__)


class FileParser(ParserProtocol[Path]):
    """
    Parser for supported local file sources.

    Responsibilities:

    - identify the source format;
    - delegate file I/O to FileReader;
    - extract logical content;
    - yield ParsedBlock objects.

    FileParser does not perform:

    - sanitization;
    - validation;
    - chunking;
    - embedding;
    - indexing;
    - persistence;
    - application orchestration.

    The parser contains no mutable per-document state and can therefore
    be safely reused across concurrent ingestion operations.
    """

    _TEXT_EXTENSIONS = frozenset({".txt", ".md"})
    _HTML_EXTENSIONS = frozenset({".html", ".htm"})

    _DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument." "wordprocessingml.document"

    def __init__(
        self,
        *,
        reader: FileReader | None = None,
    ) -> None:
        self._reader = reader or FileReader()

    def parse(
        self,
        *,
        source: Path,
    ) -> Iterator[ParsedBlock]:
        """
        Parse a supported local file incrementally.

        Raises:
            FileSourceError:
                If the source is invalid.

            IngestionError:
                If format-specific parsing fails.
        """

        self._validate_source(source)

        suffix = source.suffix.lower()

        logger.debug(
            "Starting file parsing: source=%s, suffix=%s",
            source,
            suffix,
        )

        try:
            if suffix in self._TEXT_EXTENSIONS:
                yield from self._parse_text(source)
                return

            if suffix in self._HTML_EXTENSIONS:
                yield from self._parse_html(source)
                return

            if suffix == ".pdf":
                yield from self._parse_pdf(source)
                return

            if suffix == ".docx":
                yield from self._parse_docx(source)
                return

            raise FileSourceError(
                f"Unsupported source file type: " f"{suffix or '<none>'}",
            )

        except IngestionError:
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected file parsing failure: source=%s",
                source,
            )

            raise IngestionError(
                f"Failed to parse file: {source}",
            ) from exc

        finally:
            logger.debug(
                "Finished file parsing: source=%s",
                source,
            )

    def _parse_text(
        self,
        source: Path,
    ) -> Iterator[ParsedBlock]:
        """
        Parse TXT/Markdown content using bounded FileReader chunks.
        """

        mime_type = "text/markdown" if source.suffix.lower() == ".md" else "text/plain"

        for sequence, text in enumerate(
            self._reader.read_text(source),
        ):
            if not text:
                continue

            yield ParsedBlock(
                text=text,
                source="file",
                mime_type=mime_type,
                sequence=sequence,
            )

    def _parse_html(
        self,
        source: Path,
    ) -> Iterator[ParsedBlock]:
        """
        Parse HTML content.

        NOTE:
        The current BeautifulSoup implementation requires the complete
        HTML document in memory. This is intentionally isolated and
        should be replaced with an incremental HTML parser later.
        """

        from bs4 import BeautifulSoup

        html = "".join(
            self._reader.read_text(source),
        )

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        try:
            for sequence, element in enumerate(
                soup.stripped_strings,
            ):
                if not element.strip():
                    continue

                yield ParsedBlock(
                    text=element,
                    source="file",
                    mime_type="text/html",
                    sequence=sequence,
                )
        finally:
            soup.decompose()

    def _parse_pdf(
        self,
        source: Path,
    ) -> Iterator[ParsedBlock]:
        """
        Extract PDF pages one at a time.

        ResourceContextManager owns the file handle for the complete
        lifetime of the generator.
        """

        from pypdf import PdfReader

        with ResourceContextManager() as resources:
            file_handle = self._reader.open_binary(
                source,
                resources=resources,
            )

            reader = PdfReader(file_handle)

            for sequence, page in enumerate(reader.pages):
                text = page.extract_text() or ""

                if not text.strip():
                    continue

                yield ParsedBlock(
                    text=text,
                    source="file",
                    mime_type="application/pdf",
                    sequence=sequence,
                )

    def _parse_docx(
        self,
        source: Path,
    ) -> Iterator[ParsedBlock]:
        """
        Extract DOCX paragraphs through a managed binary stream.

        python-docx may internally load package structures, so this
        should not be described as true streaming.
        """

        from docx import Document as DocxDocument

        with ResourceContextManager() as resources:
            file_handle = self._reader.open_binary(
                source,
                resources=resources,
            )

            document = DocxDocument(file_handle)

            for sequence, paragraph in enumerate(
                document.paragraphs,
            ):
                text = paragraph.text

                if not text.strip():
                    continue

                yield ParsedBlock(
                    text=text,
                    source="file",
                    mime_type=self._DOCX_MIME_TYPE,
                    sequence=sequence,
                )

    @staticmethod
    def _validate_source(
        source: Path,
    ) -> None:
        """
        Validate the source before format detection.
        """

        if not source.exists():
            raise FileSourceError(
                f"Source file does not exist: {source}",
            )

        if not source.is_file():
            raise FileSourceError(
                f"Source path is not a regular file: {source}",
            )
