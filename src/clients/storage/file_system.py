import asyncio
import hashlib
from pathlib import Path

import aiofiles

from core.exceptions.client import ClientProviderError, ClientResponseError
from src.clients.storage.base import StorageClient
from src.clients.storage.models import (
    DeleteRequest,
    DownloadRequest,
    DownloadResponse,
    ExistsRequest,
    ListRequest,
    ListResponse,
    MetadataRequest,
    StoredObject,
    UploadRequest,
    UploadResponse,
)
from src.clients.storage.paths import StoragePaths
from src.clients.storage.serializer import StorageSerializer
from src.core.enums import StorageType
from src.core.logger import get_logger

log = get_logger(__name__)


class LocalStorageClient(StorageClient):
    """
    Local filesystem storage implementation.
    """

    def __init__(
        self,
        *,
        root_directory: Path,
    ) -> None:
        self._paths = StoragePaths(
            root_directory=root_directory,
        )

        self._paths.root().mkdir(
            parents=True,
            exist_ok=True,
        )

    @property
    def storage_type(
        self,
    ) -> StorageType:
        return StorageType.LOCAL

    async def upload(
        self,
        *,
        request: UploadRequest,
    ) -> UploadResponse:
        """
        Upload an object.
        """

        log.debug(
            "Uploading '%s' into '%s'.",
            request.filename,
            request.object_id,
        )

        try:
            self._paths.ensure_object_directory(
                object_id=request.object_id,
            )

            object_file = self._paths.object_file(
                object_id=request.object_id,
                filename=request.filename,
            )

            stored_object = StoredObject(
                object_id=request.object_id,
                filename=request.filename,
                content_type=request.content_type,
                size=len(request.content),
                checksum=hashlib.sha256(
                    request.content,
                ).hexdigest(),
                storage_path=str(
                    object_file,
                ),
                metadata=request.metadata,
            )

            await self._write_object(
                stored_object=stored_object,
                content=request.content,
            )

            await self._write_metadata(
                stored_object=stored_object,
            )

            log.info(
                "Uploaded '%s' into '%s'.",
                request.filename,
                request.object_id,
            )

            return UploadResponse(
                object=stored_object,
            )

        except (
            ClientProviderError,
            ClientResponseError,
        ):
            log.exception(
                "Upload failed for '%s'.",
                request.filename,
            )
            raise

        except OSError as exc:
            log.exception(
                "Failed to upload '%s'.",
                request.filename,
            )

            raise ClientProviderError(
                message="Failed to upload object.",
            ) from exc

    async def download(
        self,
        *,
        request: DownloadRequest,
    ) -> DownloadResponse:
        """
        Download an object.
        """

        log.debug(
            "Downloading '%s' from '%s'.",
            request.filename,
            request.object_id,
        )

        stored_object = await self._read_metadata(
            object_id=request.object_id,
            filename=request.filename,
        )

        content = await self._read_object(
            stored_object=stored_object,
        )

        return DownloadResponse(
            object=stored_object,
            content=content,
        )

    async def delete(
        self,
        *,
        request: DeleteRequest,
    ) -> None:
        """
        Delete an object.
        """

        try:
            object_file = self._paths.object_file(
                object_id=request.object_id,
                filename=request.filename,
            )

            metadata_file = self._paths.metadata_file(
                object_id=request.object_id,
                filename=request.filename,
            )

            if object_file.exists():
                await asyncio.to_thread(
                    object_file.unlink,
                )

            if metadata_file.exists():
                await asyncio.to_thread(
                    metadata_file.unlink,
                )

            # Remove the conversation directory if it is now empty.
            directory = self._paths.object_directory(
                object_id=request.object_id,
            )

            if directory.exists() and not any(
                directory.iterdir(),
            ):
                await asyncio.to_thread(
                    directory.rmdir,
                )

            log.info(
                "Deleted '%s' from '%s'.",
                request.filename,
                request.object_id,
            )

        except OSError as exc:
            log.exception(
                "Failed to delete '%s'.",
                request.filename,
            )

            raise ClientProviderError(
                message="Failed to delete object.",
            ) from exc

    async def exists(
        self,
        *,
        request: ExistsRequest,
    ) -> bool:
        """
        Determine whether an object exists.
        """

        try:
            return self._paths.object_file(
                object_id=request.object_id,
                filename=request.filename,
            ).exists()

        except OSError as exc:
            log.exception(
                "Failed checking existence of '%s'.",
                request.filename,
            )

            raise ClientProviderError(
                message="Failed to determine whether object exists.",
            ) from exc

    async def metadata(
        self,
        *,
        request: MetadataRequest,
    ) -> StoredObject:
        """
        Retrieve object metadata.
        """
        log.debug(
            "Loading metadata for '%s'.",
            request.filename,
        )
        return await self._read_metadata(
            object_id=request.object_id,
            filename=request.filename,
        )

    async def list(
        self,
        *,
        request: ListRequest,
    ) -> ListResponse:
        """
        List stored objects.
        """

        objects: list[StoredObject] = []

        directory = self._paths.object_directory(
            object_id=request.object_id,
        )

        if not directory.exists():
            return ListResponse(
                objects=(),
            )

        for metadata_file in sorted(
            directory.glob("*.metadata.json"),
        ):
            try:
                async with aiofiles.open(
                    metadata_file,
                ) as file:
                    content = await file.read()

                stored_object = StorageSerializer.loads(
                    content,
                )

            except (
                ClientProviderError,
                ClientResponseError,
            ):
                log.warning(
                    "Skipping invalid metadata '%s'.",
                    metadata_file,
                )
                continue

            if request.prefix and not stored_object.filename.startswith(
                request.prefix,
            ):
                continue

            objects.append(
                stored_object,
            )

            if request.limit is not None and len(objects) >= request.limit:
                break

        return ListResponse(
            objects=tuple(objects),
        )

    async def _write_object(
        self,
        *,
        stored_object: StoredObject,
        content: bytes,
    ) -> None:
        """
        Write object content.
        """

        object_file = self._paths.object_file(
            object_id=stored_object.object_id,
            filename=stored_object.filename,
        )

        try:
            async with aiofiles.open(
                object_file,
                "wb",
            ) as file:
                await file.write(
                    content,
                )

        except OSError as exc:
            log.exception(
                "Failed writing '%s'.",
                object_file,
            )
            raise ClientProviderError(
                message="Failed to write storage object.",
            ) from exc

    async def _read_object(
        self,
        *,
        stored_object: StoredObject,
    ) -> bytes:
        """
        Read object content.
        """

        object_file = self._paths.object_file(
            object_id=stored_object.object_id,
            filename=stored_object.filename,
        )

        try:
            async with aiofiles.open(
                object_file,
                "rb",
            ) as file:
                return await file.read()

        except FileNotFoundError as exc:
            message = (
                f"File '{stored_object.filename}' "
                f"does not exist in '{stored_object.object_id}'."
            )
            log.exception(message)
            raise ClientResponseError(
                message,
            ) from exc
        except OSError as exc:
            log.exception(
                "Failed read storage metadata '%s'.",
                stored_object.filename,
            )
            raise ClientProviderError(
                message="Failed to read storage metadata.",
            ) from exc

    async def _write_metadata(
        self,
        *,
        stored_object: StoredObject,
    ) -> None:
        """
        Write object metadata.
        """

        metadata_file = self._paths.metadata_file(
            object_id=stored_object.object_id,
            filename=stored_object.filename,
        )

        try:
            async with aiofiles.open(
                metadata_file,
                "w",
            ) as file:
                await file.write(
                    StorageSerializer.dumps(
                        stored_object,
                        indent=None,
                    ),
                )

        except OSError as exc:
            log.exception(
                "Failed writing metadata of '%s'.",
                stored_object.filename,
            )
            raise ClientProviderError(
                message="Failed to write storage metadata.",
            ) from exc

    async def _read_metadata(
        self,
        *,
        object_id: str,
        filename: str,
    ) -> StoredObject:
        """
        Read object metadata.
        """

        metadata_file = self._paths.metadata_file(
            object_id=object_id,
            filename=filename,
        )

        try:
            async with aiofiles.open(
                metadata_file,
            ) as file:
                content = await file.read()

        except FileNotFoundError as exc:
            message = f"Metadata for '{filename}' " f"does not exist in '{object_id}'."

            log.exception(message)
            raise ClientResponseError(
                message,
            ) from exc
        except OSError as exc:
            log.exception(
                "Failed reading '%s'.",
                filename,
            )
            raise ClientProviderError(
                message="Failed to read storage object.",
            ) from exc

        return StorageSerializer.loads(
            content,
        )
