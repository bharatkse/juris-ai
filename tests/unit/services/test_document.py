"""
Unit tests for DocumentService.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from src.services.document import DocumentService

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.clients.storage.models import (
    DeleteRequest,
    StoredObject,
    UploadRequest,
    UploadResponse,
)
from src.core.enums import DocumentStatus, StorageType
from src.core.exceptions.client import ClientProviderError, ClientResponseError
from tests.factories.document import DocumentFactory


@pytest.mark.asyncio
async def test_upload_returns_empty_list_when_no_uploads(
    document_service: DocumentService,
    mock_document_repository: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """
    It should return an empty list when no uploads are provided.
    """

    documents = await document_service.upload(
        conversation_id="conv_123",
        uploads=[],
    )

    assert documents == []

    mock_storage_client.upload.assert_not_called()
    mock_document_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_uploads_document(
    document_service: DocumentService,
    mock_document_repository: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """
    It should upload a document and persist its metadata.
    """

    upload = UploadRequest(
        object_id="obj_123",
        filename="contract.pdf",
        content=b"content",
        content_type="application/pdf",
    )

    stored = StoredObject(
        object_id="obj_123",
        filename="stored.pdf",
        storage_path="documents/stored.pdf",
        checksum="checksum",
        size=7,
        content_type="application/pdf",
    )

    mock_storage_client.storage_type = StorageType.LOCAL

    mock_storage_client.upload.return_value = UploadResponse(
        object=stored,
    )

    mock_document_repository.create.side_effect = lambda document: document

    documents = await document_service.upload(
        conversation_id="conv_123",
        uploads=[upload],
    )

    assert len(documents) == 1

    document = documents[0]

    assert document.conversation_id == "conv_123"
    assert document.original_filename == upload.filename
    assert document.filename == stored.filename
    assert document.mime_type == stored.content_type
    assert document.size == stored.size
    assert document.storage_path == stored.storage_path
    assert document.checksum == stored.checksum
    assert document.storage_type == StorageType.LOCAL
    assert document.status == DocumentStatus.UPLOADED

    mock_storage_client.upload.assert_awaited_once()
    mock_document_repository.create.assert_awaited_once()

    created_document = mock_document_repository.create.await_args.kwargs["document"]

    assert created_document.original_filename == upload.filename
    assert created_document.conversation_id == "conv_123"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception",
    [
        ClientProviderError("provider"),
        ClientResponseError("response"),
        SQLAlchemyError("database"),
    ],
)
async def test_upload_cleans_up_when_upload_fails(
    document_service: DocumentService,
    mock_storage_client: MagicMock,
    exception: Exception,
) -> None:
    """
    It should clean up uploaded files when upload fails.
    """

    upload = UploadRequest(
        object_id="obj_123",
        filename="contract.pdf",
        content=b"content",
        content_type="application/pdf",
    )

    stored = StoredObject(
        object_id="obj_123",
        filename="stored.pdf",
        storage_path="documents/stored.pdf",
        checksum="checksum",
        size=7,
        content_type="application/pdf",
    )

    mock_storage_client.storage_type = StorageType.LOCAL

    mock_storage_client.upload.side_effect = [
        UploadResponse(
            object=stored,
        ),
        exception,
    ]

    with pytest.raises(type(exception)):
        await document_service.upload(
            conversation_id="conv_123",
            uploads=[
                upload,
                upload,
            ],
        )

    mock_storage_client.delete.assert_awaited_once()

    request = mock_storage_client.delete.await_args.kwargs["request"]

    assert isinstance(
        request,
        DeleteRequest,
    )

    assert request.object_id == stored.object_id
    assert request.filename == stored.filename


@pytest.mark.asyncio
async def test_get_returns_document(
    document_service: DocumentService,
    mock_document_repository: MagicMock,
) -> None:
    """
    It should return the requested document.
    """

    document = DocumentFactory.build()

    mock_document_repository.get.return_value = document

    found = await document_service.get(
        document_id=document.id,
    )

    assert found is document

    mock_document_repository.get.assert_awaited_once_with(
        document_id=document.id,
    )


@pytest.mark.asyncio
async def test_list_returns_documents(
    document_service: DocumentService,
    mock_document_repository: MagicMock,
) -> None:
    """
    It should return documents for a conversation.
    """

    documents = DocumentFactory.build_batch(
        2,
    )

    mock_document_repository.list_by_conversation.return_value = documents

    found = await document_service.list(
        conversation_id="conv_123",
    )

    assert found == documents

    mock_document_repository.list_by_conversation.assert_awaited_once_with(
        conversation_id="conv_123",
    )


@pytest.mark.asyncio
async def test_cleanup_uploads_deletes_uploaded_objects(
    document_service: DocumentService,
    mock_storage_client: MagicMock,
) -> None:
    """
    It should delete uploaded objects.
    """

    stored = StoredObject(
        object_id="obj_123",
        filename="stored.pdf",
        storage_path="documents/stored.pdf",
        checksum="checksum",
        size=7,
        content_type="application/pdf",
    )

    await document_service._cleanup_uploads(
        uploaded_objects=[
            stored,
        ],
    )

    mock_storage_client.delete.assert_awaited_once()

    request = mock_storage_client.delete.await_args.kwargs["request"]

    assert request.object_id == stored.object_id
    assert request.filename == stored.filename


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception",
    [
        ClientProviderError("provider"),
        ClientResponseError("response"),
    ],
)
async def test_cleanup_uploads_ignores_delete_failures(
    document_service: DocumentService,
    mock_storage_client: MagicMock,
    exception: Exception,
) -> None:
    """
    It should ignore cleanup failures.
    """

    stored = StoredObject(
        object_id="obj_123",
        filename="stored.pdf",
        storage_path="documents/stored.pdf",
        checksum="checksum",
        size=7,
        content_type="application/pdf",
    )

    mock_storage_client.delete.side_effect = exception

    await document_service._cleanup_uploads(
        uploaded_objects=[
            stored,
        ],
    )

    mock_storage_client.delete.assert_awaited_once()
