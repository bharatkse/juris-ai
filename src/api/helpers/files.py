from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from core.dto.tool import ToolFileDTO

MAX_CHAT_FILES = 5
MAX_CHAT_FILE_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_CHAT_FILE_EXTENSIONS = {
    ".docx",
    ".html",
    ".md",
    ".pdf",
    ".text",
    ".txt",
}


async def build_tool_files(
    files: list[UploadFile],
) -> tuple[ToolFileDTO, ...]:
    if len(files) > MAX_CHAT_FILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A maximum of {MAX_CHAT_FILES} files may be attached.",
        )

    tool_files: list[ToolFileDTO] = []

    for file in files:
        filename = file.filename or "unknown"
        extension = Path(filename).suffix.lower()

        if extension not in ALLOWED_CHAT_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    "Unsupported file type. Upload PDF, DOCX, TXT, MD, or HTML files."
                ),
            )

        content = await file.read(
            MAX_CHAT_FILE_SIZE_BYTES + 1,
        )

        if len(content) > MAX_CHAT_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Each attachment must be 20 MB or smaller.",
            )

        tool_files.append(
            ToolFileDTO(
                filename=filename,
                content=content,
                content_type=file.content_type or "application/octet-stream",
            ),
        )

    return tuple(tool_files)
