"""
LibraryFile service.
"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.clients.storage.base import StorageClient
from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.models.library_file import LibraryFile
from adapters.persistence.sqlalchemy.repositories.library_file import (
    LibraryFileRepository,
)
from application.services.base import BaseService
from core.dto.clients.storage import (
    DeleteRequestDTO,
    StoredObjectDTO,
    UploadRequestDTO,
)
from core.enums import LibraryFileStatusEnum
from core.exceptions.client import ClientProviderError, ClientResponseError

log = get_logger(__name__)


class LibraryFileService(BaseService):
    """
    Manage user-uploaded files.

    This service owns the upload/storage lifecycle and persistence
    of LibraryFile metadata.

    It does not own:
        - document parsing
        - chunking
        - embeddings
        - vector search
        - RAG
        - LLM context construction
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: LibraryFileRepository,
        storage: StorageClient,
    ) -> None:
        super().__init__(session)

        self._repository = repository
        self._storage = storage

    async def upload(
        self,
        *,
        conversation_id: str,
        uploads: list[UploadRequestDTO],
    ) -> list[LibraryFile]:
        """
        Upload files and persist their metadata.

        Uploaded files remain transactional user artifacts.
        Any subsequent document understanding or context-engineering
        workflow is handled outside this service.
        """

        if not uploads:
            return []

        log.info(
            "Uploading %d file(s) for conversation '%s'.",
            len(uploads),
            conversation_id,
        )

        uploaded_objects: list[StoredObjectDTO] = []
        library_files: list[LibraryFile] = []

        try:
            async with self._session.begin():
                for request in uploads:
                    response = await self._storage.upload(
                        request=request,
                    )

                    stored = response.object

                    uploaded_objects.append(stored)

                    library_file = LibraryFile(
                        conversation_id=conversation_id,
                        source_type=request.source_type,
                        original_filename=request.filename,
                        filename=stored.filename,
                        mime_type=stored.content_type,
                        size=stored.size,
                        checksum=stored.checksum,
                        storage_type=self._storage.storage_type,
                        storage_path=stored.storage_path,
                        status=LibraryFileStatusEnum.UPLOADED,
                    )

                    await self._repository.create(
                        library_file=library_file,
                    )

                    library_files.append(library_file)

            log.info(
                "Uploaded %d file(s) for conversation '%s'.",
                len(library_files),
                conversation_id,
            )

            return library_files

        except (
            ClientProviderError,
            ClientResponseError,
            SQLAlchemyError,
        ):
            log.exception(
                "Failed to upload file(s) for conversation '%s'.",
                conversation_id,
            )

            await self._cleanup_uploads(
                uploaded_objects=uploaded_objects,
            )

            raise

    async def get_by_id(
        self,
        *,
        library_file_id: str,
    ) -> LibraryFile | None:
        """
        Retrieve an uploaded file by identifier.
        """

        return await self._repository.get_by_id(
            library_file_id=library_file_id,
        )

    async def list(
        self,
        *,
        conversation_id: str,
    ) -> list[LibraryFile]:
        """
        Retrieve all uploaded files for a conversation.
        """

        return await self._repository.list_by_conversation(
            conversation_id=conversation_id,
        )

    async def delete(
        self,
        *,
        library_file: LibraryFile,
    ) -> None:
        """
        Delete an uploaded file from storage and persistence.
        """

        if library_file.storage_path:
            await self._storage.delete(
                request=DeleteRequestDTO(
                    object_id=library_file.id,
                    filename=library_file.filename,
                ),
            )

        await self._repository.delete(
            library_file,
        )

    async def _cleanup_uploads(
        self,
        *,
        uploaded_objects: list[StoredObjectDTO],
    ) -> None:
        """
        Remove uploaded files from storage after a failed transaction.
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
