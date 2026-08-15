from __future__ import annotations

from fastapi import UploadFile

from src.core.dto.tool import ToolFileDTO


async def build_tool_files(
    files: list[UploadFile],
) -> tuple[ToolFileDTO, ...]:
    tool_files: list[ToolFileDTO] = []

    for file in files:
        tool_files.append(
            ToolFileDTO(
                filename=file.filename or "unknown",
                content=await file.read(),
                content_type=file.content_type or "application/octet-stream",
            ),
        )

    return tuple(tool_files)
