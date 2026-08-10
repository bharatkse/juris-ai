"""
Document parser tool.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from io import BytesIO
from types import MappingProxyType

from docx import Document
from pypdf import PdfReader

from core.models.tool import (
    RetrievedContent,
    ToolFile,
    ToolMetadata,
    ToolRequest,
    ToolResponse,
)
from src.core.enums import RetrievalSource
from src.core.exceptions.tool import ToolValidationError
from src.tools.base import BaseTool
from src.tools.constants import (
    DOCX_CONTENT_TYPE,
    MARKDOWN_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    TEXT_CONTENT_TYPE,
)


class ParserTool(BaseTool):
    """
    Parse uploaded documents into plain text.
    """

    metadata = ToolMetadata(
        name="parser",
        description="Parse uploaded documents into plain text.",
    )

    def __init__(self) -> None:
        self._parsers: Mapping[
            str,
            Callable[[ToolFile], str],
        ] = MappingProxyType(
            {
                PDF_CONTENT_TYPE: self._parse_pdf,
                DOCX_CONTENT_TYPE: self._parse_docx,
                TEXT_CONTENT_TYPE: self._parse_text,
                MARKDOWN_CONTENT_TYPE: self._parse_text,
            },
        )

    async def run(
        self,
        *,
        request: ToolRequest,
    ) -> ToolResponse:
        """
        Parse uploaded documents.
        """

        content = tuple(
            self._parse(
                file=file,
            )
            for file in request.uploaded_files
        )

        return ToolResponse(
            content=content,
        )

    def _parse(
        self,
        *,
        file: ToolFile,
    ) -> RetrievedContent:
        """
        Parse a single uploaded document.
        """

        parser = self._parsers.get(
            file.content_type,
        )

        if parser is None:
            raise ToolValidationError(
                message=(
                    f"Unsupported content type "
                    f"'{file.content_type}' "
                    f"for file '{file.filename}'."
                ),
            )

        return RetrievedContent(
            source=RetrievalSource.DOCUMENT,
            content=parser(file),
            metadata={
                "filename": file.filename,
                "content_type": file.content_type,
                **file.metadata,
            },
        )

    @staticmethod
    def _parse_pdf(
        file: ToolFile,
    ) -> str:
        """
        Parse a PDF document.
        """

        reader = PdfReader(
            BytesIO(file.content),
        )

        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()

    @staticmethod
    def _parse_docx(
        file: ToolFile,
    ) -> str:
        """
        Parse a DOCX document.
        """

        document = Document(
            BytesIO(file.content),
        )

        return "\n".join(
            paragraph.text for paragraph in document.paragraphs if paragraph.text
        ).strip()

    @staticmethod
    def _parse_text(
        file: ToolFile,
    ) -> str:
        """
        Parse a text or Markdown document.
        """

        return file.content.decode(
            "utf-8",
            errors="replace",
        ).strip()
