"""
Unit tests for LibraryService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from adapters.clients.storage.base import StorageClient
from adapters.persistence.sqlalchemy.models.library import Library
from application.services.library import LibraryService
from core.dto.clients.storage import (
    DeleteRequestDTO,
    StoredObjectDTO,
    UploadRequestDTO,
    UploadResponseDTO,
)
from core.enums import LibrarySourceEnum, LibraryStatusEnum, StorageTypeEnum


def _session() -> MagicMock:
    session = MagicMock()
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=False)
    session.begin.return_value = transaction
    return session


def _storage() -> AsyncMock:
    storage = AsyncMock(spec=StorageClient)
    storage.storage_type = StorageTypeEnum.LOCAL

    async def upload(*, request: UploadRequestDTO) -> UploadResponseDTO:
        return UploadResponseDTO(
            object=StoredObjectDTO(
                object_id=request.object_id,
                filename=f"stored-{request.filename}",
                content_type=request.content_type,
                size=len(request.content),
                checksum="abc",
                storage_path=f"/data/{request.object_id}/stored-{request.filename}",
            ),
        )

    storage.upload.side_effect = upload
    return storage


def _upload(filename: str) -> UploadRequestDTO:
    return UploadRequestDTO(
        object_id="conv-1",
        filename=filename,
        content=b"hello",
        content_type="text/plain",
    )


def _service(*, storage: AsyncMock, repository: AsyncMock | None = None) -> LibraryService:
    return LibraryService(
        session=_session(),
        repository=repository or AsyncMock(),
        storage=storage,
    )


async def test_upload_returns_one_library_row_per_file() -> None:
    repository = AsyncMock()
    service = _service(storage=_storage(), repository=repository)

    libraries = await service.upload(
        conversation_id="conv-1",
        uploads=[_upload("a.txt"), _upload("b.txt")],
    )

    assert [library.original_filename for library in libraries] == ["a.txt", "b.txt"]
    assert all(isinstance(library, Library) for library in libraries)
    assert repository.create.await_count == 2


async def test_upload_persists_stored_object_metadata_as_user_file() -> None:
    service = _service(storage=_storage())

    (library,) = await service.upload(conversation_id="conv-1", uploads=[_upload("a.txt")])

    assert library.conversation_id == "conv-1"
    assert library.source_type is LibrarySourceEnum.FILE
    assert library.status is LibraryStatusEnum.UPLOADED
    assert library.filename == "stored-a.txt"
    assert library.storage_path == "/data/conv-1/stored-a.txt"
    assert library.size == 5


async def test_upload_with_no_files_does_nothing() -> None:
    storage = _storage()
    service = _service(storage=storage)

    assert await service.upload(conversation_id="conv-1", uploads=[]) == []
    storage.upload.assert_not_awaited()


async def test_failed_persist_removes_already_uploaded_objects() -> None:
    storage = _storage()
    repository = AsyncMock()
    repository.create.side_effect = [None, SQLAlchemyError("insert failed")]
    service = _service(storage=storage, repository=repository)

    with pytest.raises(SQLAlchemyError):
        await service.upload(
            conversation_id="conv-1",
            uploads=[_upload("a.txt"), _upload("b.txt")],
        )

    deleted = [call.kwargs["request"] for call in storage.delete.await_args_list]
    assert deleted == [
        DeleteRequestDTO(object_id="conv-1", filename="stored-a.txt"),
        DeleteRequestDTO(object_id="conv-1", filename="stored-b.txt"),
    ]


async def test_delete_removes_stored_object_and_row() -> None:
    storage = _storage()
    repository = AsyncMock()
    service = _service(storage=storage, repository=repository)
    library = Library(id="lib-1", filename="stored-a.txt", storage_path="/data/x")

    await service.delete(library=library)

    storage.delete.assert_awaited_once_with(
        request=DeleteRequestDTO(object_id="lib-1", filename="stored-a.txt"),
    )
    repository.delete.assert_awaited_once_with(library)


async def test_delete_without_stored_object_only_removes_row() -> None:
    storage = _storage()
    repository = AsyncMock()
    service = _service(storage=storage, repository=repository)
    library = Library(id="lib-1", filename=None, storage_path=None)

    await service.delete(library=library)

    storage.delete.assert_not_awaited()
    repository.delete.assert_awaited_once_with(library)
