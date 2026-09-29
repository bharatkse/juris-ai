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

    library_file = UploadFile(
        filename="contract.pdf",
        file=BytesIO(b"contract content"),
        headers={
            "content-type": "application/pdf",
        },
    )

    result = await build_tool_files(
        [library_file],
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


# ---------------------------------------------------------------------------
# Upload limits (review R15)
# ---------------------------------------------------------------------------


class _TrackedFile(BytesIO):
    """Records how much of the upload was read."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size: int | None = -1) -> bytes:
        chunk = super().read(size)
        self.bytes_read += len(chunk)
        return chunk


def _upload(name: str, data: bytes, *, size: int | None = -1) -> UploadFile:
    file = _TrackedFile(data)
    return UploadFile(
        filename=name,
        file=file,
        size=len(data) if size == -1 else size,
        headers={"content-type": "text/plain"},
    )


@pytest.fixture
def limits(monkeypatch: pytest.MonkeyPatch):
    from config.settings import get_settings

    settings = get_settings().rate_limit
    monkeypatch.setattr(settings, "UPLOAD_MAX_FILES", 2)
    monkeypatch.setattr(settings, "UPLOAD_MAX_FILE_BYTES", 10)
    return settings


def test_the_default_limits_are_five_files_of_ten_megabytes() -> None:
    from config.rate_limit import RateLimitSettings

    settings = RateLimitSettings()

    assert settings.UPLOAD_MAX_FILES == 5
    assert settings.UPLOAD_MAX_FILE_BYTES == 10 * 1024 * 1024


@pytest.mark.asyncio
async def test_files_within_both_limits_are_read(limits) -> None:
    result = await build_tool_files([_upload("a.txt", b"0123456789"), _upload("b.txt", b"x")])

    assert [file.content for file in result] == [b"0123456789", b"x"]


@pytest.mark.asyncio
async def test_too_many_files_are_refused_before_any_is_read(limits) -> None:
    from core.exceptions.rate_limit import TooManyUploadsError

    uploads = [_upload(f"{index}.txt", b"x") for index in range(3)]

    with pytest.raises(TooManyUploadsError) as raised:
        await build_tool_files(uploads)

    assert raised.value.status_code == 422
    assert raised.value.error_code == "TOO_MANY_UPLOADS"
    assert "At most 2 files" in raised.value.message
    assert all(upload.file.bytes_read == 0 for upload in uploads)


@pytest.mark.asyncio
async def test_a_file_over_the_size_limit_is_refused_without_reading_it(limits) -> None:
    from core.exceptions.rate_limit import UploadTooLargeError

    upload = _upload("big.pdf", b"x" * 11)

    with pytest.raises(UploadTooLargeError) as raised:
        await build_tool_files([upload])

    assert raised.value.status_code == 413
    assert raised.value.error_code == "UPLOAD_TOO_LARGE"
    assert "big.pdf" in raised.value.message
    assert upload.file.bytes_read == 0


@pytest.mark.asyncio
async def test_a_file_of_unknown_size_is_read_only_just_past_the_limit(limits) -> None:
    from core.exceptions.rate_limit import UploadTooLargeError

    upload = _upload("stream.bin", b"x" * 1000, size=None)

    with pytest.raises(UploadTooLargeError):
        await build_tool_files([upload])

    assert upload.file.bytes_read == 11
