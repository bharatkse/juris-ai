"""
Library service.
"""

from __future__ import annotations

import builtins

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.clients.storage.base import StorageClient
from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.models.library import Library
from adapters.persistence.sqlalchemy.repositories.library import (
    LibraryRepository,
)
from application.services.base import BaseService
from core.dto.clients.storage import (
    DeleteRequestDTO,
    StoredObjectDTO,
    UploadRequestDTO,
)
from core.enums import LibrarySourceEnum, LibraryStatusEnum
from core.exceptions.client import ClientProviderError, ClientResponseError

log = get_logger(__name__)


class LibraryService(BaseService):
    """
    Manage user-uploaded files.

    This service owns the upload/storage lifecycle and persistence
    of Library metadata.

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
        repository: LibraryRepository,
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
    ) -> list[Library]:
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
        libraries: list[Library] = []

        try:
            async with self._session.begin():
                for request in uploads:
                    response = await self._storage.upload(
                        request=request,
                    )

                    stored = response.object

                    uploaded_objects.append(stored)

                    library = Library(
                        conversation_id=conversation_id,
                        # Everything this service stores is a user file
                        # upload; UploadRequestDTO carries no source type.
                        source_type=LibrarySourceEnum.FILE,
                        original_filename=request.filename,
                        filename=stored.filename,
                        mime_type=stored.content_type,
                        size=stored.size,
                        checksum=stored.checksum,
                        storage_type=self._storage.storage_type,
                        storage_path=stored.storage_path,
                        status=LibraryStatusEnum.UPLOADED,
                    )

                    await self._repository.create(
                        library=library,
                    )

                    libraries.append(library)

            log.info(
                "Uploaded %d file(s) for conversation '%s'.",
                len(libraries),
                conversation_id,
            )

            return libraries

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
        library_id: str,
    ) -> Library | None:
        """
        Retrieve an uploaded file by identifier.
        """

        return await self._repository.get_by_id(
            library_id=library_id,
        )

    async def list(
        self,
        *,
        conversation_id: str,
    ) -> list[Library]:
        """
        Retrieve all uploaded files for a conversation.
        """

        return await self._repository.list_by_conversation(
            conversation_id=conversation_id,
        )

    async def delete(
        self,
        *,
        library: Library,
    ) -> None:
        """
        Delete an uploaded file from storage and persistence.
        """

        if library.storage_path and library.filename:
            await self._storage.delete(
                request=DeleteRequestDTO(
                    object_id=library.id,
                    filename=library.filename,
                ),
            )

        await self._repository.delete(
            library,
        )

    async def _cleanup_uploads(
        self,
        *,
        uploaded_objects: builtins.list[StoredObjectDTO],
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
