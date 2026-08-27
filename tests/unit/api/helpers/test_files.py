"""
Unit tests for API file helpers.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile

from api.helpers.files import build_tool_files
from core.dto.tool import ToolFileDTO


@pytest.mark.asyncio
async def test_build_tool_files_returns_empty_tuple_without_files() -> None:
    """
    It should return an empty tuple when no files are provided.
    """

    result = await build_tool_files(
        [],
    )

    assert result == ()


@pytest.mark.asyncio
async def test_build_tool_files_converts_uploaded_file() -> None:
    """
    It should convert an uploaded file into a ToolFileDTO.
    """

    upload_file = UploadFile(
        filename="contract.pdf",
        file=BytesIO(b"contract content"),
        headers={
            "content-type": "application/pdf",
        },
    )

    result = await build_tool_files(
        [upload_file],
    )

    assert result == (
        ToolFileDTO(
            filename="contract.pdf",
            content=b"contract content",
            content_type="application/pdf",
        ),
    )


@pytest.mark.asyncio
async def test_build_tool_files_preserves_file_order() -> None:
    """
    It should preserve the order of uploaded files.
    """

    first_file = UploadFile(
        filename="contract.pdf",
        file=BytesIO(b"contract"),
        headers={
            "content-type": "application/pdf",
        },
    )

    second_file = UploadFile(
        filename="evidence.txt",
        file=BytesIO(b"evidence"),
        headers={
            "content-type": "text/plain",
        },
    )

    result = await build_tool_files(
        [
            first_file,
            second_file,
        ],
    )

    assert result == (
        ToolFileDTO(
            filename="contract.pdf",
            content=b"contract",
            content_type="application/pdf",
        ),
        ToolFileDTO(
            filename="evidence.txt",
            content=b"evidence",
            content_type="text/plain",
        ),
    )
