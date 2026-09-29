from __future__ import annotations

from fastapi import UploadFile

from config.settings import get_settings
from core.constants import SUPPORTED_UPLOAD_CONTENT_TYPES
from core.dto.tool import ToolFileDTO
from core.exceptions.rate_limit import (
    TooManyUploadsError,
    UnsupportedUploadTypeError,
    UploadTooLargeError,
)


def _media_type(content_type: str | None) -> str:
    """
    The bare, lower-case media type: "text/plain; charset=utf-8" is
    "text/plain". ParserTool matches the bare type exactly.
    """

    return (content_type or "").split(";", 1)[0].strip().lower()


async def build_tool_files(
    files: list[UploadFile],
) -> tuple[ToolFileDTO, ...]:
    """
    Read the files attached to a chat message, within the upload limits
    (settings.rate_limit.UPLOAD_MAX_FILES / UPLOAD_MAX_FILE_BYTES) and of
    a type the parser reads (SUPPORTED_UPLOAD_CONTENT_TYPES: PDF, DOCX,
    plain text, Markdown).

    Every limit is checked before a file is read into memory: nothing is
    read when any file is of another type, a file whose size is known
    and over the limit is never read, and one whose size isn't known is
    read only up to one byte past the limit. The type is the one the
    client declared, reduced to its bare media type; the parser relies
    on the same value.
    """

    settings = get_settings().rate_limit

    if len(files) > settings.UPLOAD_MAX_FILES:
        raise TooManyUploadsError(
            limit=settings.UPLOAD_MAX_FILES,
            received=len(files),
        )

    for file in files:
        content_type = _media_type(file.content_type)

        if content_type not in SUPPORTED_UPLOAD_CONTENT_TYPES:
            raise UnsupportedUploadTypeError(
                filename=file.filename or "unknown",
                content_type=content_type or "none",
                supported=SUPPORTED_UPLOAD_CONTENT_TYPES,
            )

    tool_files: list[ToolFileDTO] = []

    for file in files:
        filename = file.filename or "unknown"

        if file.size is not None and file.size > settings.UPLOAD_MAX_FILE_BYTES:
            raise UploadTooLargeError(
                filename=filename,
                limit_bytes=settings.UPLOAD_MAX_FILE_BYTES,
            )

        content = await file.read(settings.UPLOAD_MAX_FILE_BYTES + 1)

        if len(content) > settings.UPLOAD_MAX_FILE_BYTES:
            raise UploadTooLargeError(
                filename=filename,
                limit_bytes=settings.UPLOAD_MAX_FILE_BYTES,
            )

        tool_files.append(
            ToolFileDTO(
                filename=filename,
                content=content,
                content_type=_media_type(file.content_type),
            ),
        )

    return tuple(tool_files)
