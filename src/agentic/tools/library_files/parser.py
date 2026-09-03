"""
Document parser tool.

_parse_one wraps synchronous, CPU-bound work (PdfReader page
extraction, python-docx paragraph iteration) — both can take real
wall-clock time on a large file. Running that directly inside
async def execute() blocks the single-threaded asyncio event loop for
every other concurrent request on the same process for the entire
duration, not just this one. asyncio.to_thread offloads it to a
worker thread so the event loop stays free to serve other requests
while a big PDF parses.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from io import BytesIO
from types import MappingProxyType

from docx import Document
from pypdf import PdfReader

from adapters.observability.logger import get_logger
from agentic.tools.base import Tool
from agentic.tools.constants import (
    DOCX_CONTENT_TYPE,
    MARKDOWN_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    TEXT_CONTENT_TYPE,
)
from core.dto.tool import ToolFileDTO

log = get_logger(__name__)


class ParserTool(Tool):
    """
    Parse uploaded documents into plain text.
    """

    name = "parser"
    description = "Parse uploaded documents (PDF, DOCX, text, Markdown) into plain text."

    def __init__(self) -> None:
        self._parsers: Mapping[str, Callable[[ToolFileDTO], str]] = MappingProxyType(
            {
                PDF_CONTENT_TYPE: self._parse_pdf,
                DOCX_CONTENT_TYPE: self._parse_docx,
                TEXT_CONTENT_TYPE: self._parse_text,
                MARKDOWN_CONTENT_TYPE: self._parse_text,
            }
        )

    async def execute(self, *, files: list[ToolFileDTO]) -> str:
        """
        Parse one or more uploaded files. A single corrupted/
        unsupported file does not fail the whole batch — its block
        reports the error instead, matching the per-item failure
        isolation pattern used in content_fetch.py.
        """

        if not files:
            return "No files provided to parse."

        # Each file parsed in its own thread, concurrently — a batch
        # of several files doesn't serialize behind each other, and
        # none of them block the event loop.
        blocks = await asyncio.gather(
            *(asyncio.to_thread(self._parse_one, file=file) for file in files)
        )

        return "\n\n---\n\n".join(blocks)

    def _parse_one(self, *, file: ToolFileDTO) -> str:
        """
        Runs inside a worker thread (via asyncio.to_thread) — must
        stay synchronous.
        """

        parser = self._parsers.get(file.content_type)

        if parser is None:
            log.warning(
                "Unsupported content type '%s' for file '%s'.",
                file.content_type,
                file.filename,
            )
            return f"[{file.filename}]: unsupported content type '{file.content_type}'."

        try:
            text = parser(file)

        except Exception:
            log.exception(
                "Failed to parse file '%s' (content_type=%s).",
                file.filename,
                file.content_type,
            )
            return f"[{file.filename}]: failed to parse — file may be corrupted."

        if not text:
            log.warning("Parsed empty content from file '%s'.", file.filename)
            return f"[{file.filename}]: no extractable text."

        return f"[{file.filename}]\n{text}"

    @staticmethod
    def _parse_pdf(file: ToolFileDTO) -> str:
        reader = PdfReader(BytesIO(file.content))

        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()

    @staticmethod
    def _parse_docx(file: ToolFileDTO) -> str:
        document = Document(BytesIO(file.content))

        return "\n".join(
            paragraph.text for paragraph in document.paragraphs if paragraph.text
        ).strip()

    @staticmethod
    def _parse_text(file: ToolFileDTO) -> str:
        return file.content.decode("utf-8", errors="replace").strip()
