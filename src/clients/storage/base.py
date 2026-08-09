"""
Base storage client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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
from src.core.enums import StorageType


class StorageClient(ABC):
    """
    Base class for storage providers.
    """

    @property
    @abstractmethod
    def storage_type(self) -> StorageType:
        """
        Storage provider type.
        """

    @abstractmethod
    async def upload(
        self,
        *,
        request: UploadRequest,
    ) -> UploadResponse: ...

    @abstractmethod
    async def download(
        self,
        *,
        request: DownloadRequest,
    ) -> DownloadResponse: ...

    @abstractmethod
    async def delete(
        self,
        *,
        request: DeleteRequest,
    ) -> None: ...

    @abstractmethod
    async def exists(
        self,
        *,
        request: ExistsRequest,
    ) -> bool: ...

    @abstractmethod
    async def metadata(
        self,
        *,
        request: MetadataRequest,
    ) -> StoredObject: ...

    @abstractmethod
    async def list(
        self,
        *,
        request: ListRequest,
    ) -> ListResponse: ...
