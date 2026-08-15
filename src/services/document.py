"""
Document service.
"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.storage.base import StorageClient
from src.core.dto.clients.storage import (
    DeleteRequestDTO,
    StoredObjectDTO,
    UploadRequestDTO,
)
from src.core.enums import DocumentStatusEnum
from src.core.exceptions.client import ClientProviderError, ClientResponseError
from src.core.logger import get_logger
from src.db.models.document import Document
from src.repositories.document import DocumentRepository

log = get_logger(__name__)


class DocumentService:
    """
    Manage uploaded documents.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: DocumentRepository,
        storage: StorageClient,
    ) -> None:
        self._session = session
        self._repository = repository
        self._storage = storage

    async def upload(
        self,
        *,
        conversation_id: str,
        uploads: list[UploadRequestDTO],
    ) -> list[Document]:
        """
        Upload documents and persist metadata.
        """

        if not uploads:
            return []

        log.info(
            "Uploading %d document(s) for conversation '%s'.",
            len(uploads),
            conversation_id,
        )

        uploaded_objects: list[StoredObjectDTO] = []
        documents: list[Document] = []

        try:
            async with self._session.begin():
                for request in uploads:
                    response = await self._storage.upload(
                        request=request,
                    )

                    stored = response.object

                    uploaded_objects.append(
                        stored,
                    )

                    document = Document(
                        conversation_id=conversation_id,
                        original_filename=request.filename,
                        filename=stored.filename,
                        mime_type=stored.content_type,
                        size=stored.size,
                        checksum=stored.checksum,
                        storage_type=self._storage.storage_type,
                        storage_path=stored.storage_path,
                        status=DocumentStatusEnum.UPLOADED,
                    )

                    await self._repository.create(
                        document=document,
                    )

                    documents.append(
                        document,
                    )

            log.info(
                "Uploaded %d document(s) for conversation '%s'.",
                len(documents),
                conversation_id,
            )

            return documents

        except (
            ClientProviderError,
            ClientResponseError,
            SQLAlchemyError,
        ):
            log.exception(
                "Failed to upload document(s) for conversation '%s'.",
                conversation_id,
            )

            await self._cleanup_uploads(
                uploaded_objects=uploaded_objects,
            )

            raise

    async def get(
        self,
        *,
        document_id: str,
    ) -> Document | None:
        """
        Retrieve a document.
        """

        return await self._repository.get(
            document_id=document_id,
        )

    async def list(
        self,
        *,
        conversation_id: str,
    ) -> list[Document]:
        """
        Retrieve all documents for a conversation.
        """

        return await self._repository.list_by_conversation(
            conversation_id=conversation_id,
        )

    async def _cleanup_uploads(
        self,
        *,
        uploaded_objects: list[StoredObjectDTO],
    ) -> None:
        """
        Remove uploaded files after a failed transaction.
        """

        for stored in uploaded_objects:
            try:
                await self._storage.delete(
                    request=DeleteRequestDTO(
                        object_id=stored.object_id,
                        filename=stored.filename,
                    ),
                )

                log.info(
                    "Cleaned up '%s'.",
                    stored.filename,
                )

            except (
                ClientProviderError,
                ClientResponseError,
            ):
                log.exception(
                    "Failed to clean up '%s'.",
                    stored.filename,
                )
