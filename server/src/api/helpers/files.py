from __future__ import annotations

from fastapi import UploadFile

from config.settings import get_settings
from core.dto.tool import ToolFileDTO
from core.exceptions.rate_limit import TooManyUploadsError, UploadTooLargeError


async def build_tool_files(
    files: list[UploadFile],
) -> tuple[ToolFileDTO, ...]:
    """
    Read the files attached to a chat message, within the upload limits
    (settings.rate_limit.UPLOAD_MAX_FILES / UPLOAD_MAX_FILE_BYTES).

    Both limits are checked before a file is read into memory: a file
    whose size is known and over the limit is never read, and one whose
    size isn't known is read only up to one byte past the limit.
    """

    settings = get_settings().rate_limit

    if len(files) > settings.UPLOAD_MAX_FILES:
        raise TooManyUploadsError(
            limit=settings.UPLOAD_MAX_FILES,
            received=len(files),
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
                content_type=file.content_type or "application/octet-stream",
            ),
        )

    return tuple(tool_files)
