"""
Base storage client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.dto.clients.storage import (
    DeleteRequestDTO,
    DownloadRequestDTO,
    DownloadResponseDTO,
    ExistsRequestDTO,
    ListRequestDTO,
    ListResponseDTO,
    MetadataRequestDTO,
    StoredObjectDTO,
    UploadRequestDTO,
    UploadResponseDTO,
)
from src.core.enums import StorageTypeEnum


class StorageClient(ABC):
    """
    Base class for storage providers.
    """

    @property
    @abstractmethod
    def storage_type(self) -> StorageTypeEnum:
        """
        Storage provider type.
        """

    @abstractmethod
    async def upload(
        self,
        *,
        request: UploadRequestDTO,
    ) -> UploadResponseDTO: ...

    @abstractmethod
    async def download(
        self,
        *,
        request: DownloadRequestDTO,
    ) -> DownloadResponseDTO: ...

    @abstractmethod
    async def delete(
        self,
        *,
        request: DeleteRequestDTO,
    ) -> None: ...

    @abstractmethod
    async def exists(
        self,
        *,
        request: ExistsRequestDTO,
    ) -> bool: ...

    @abstractmethod
    async def metadata(
        self,
        *,
        request: MetadataRequestDTO,
    ) -> StoredObjectDTO: ...

    @abstractmethod
    async def list(
        self,
        *,
        request: ListRequestDTO,
    ) -> ListResponseDTO: ...
