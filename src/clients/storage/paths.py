"""
Storage path utilities.
"""

from __future__ import annotations

from pathlib import Path

from src.core.custom_exceptions.client import ClientProviderError
from src.core.logger import get_logger

log = get_logger(__name__)


class StoragePaths:
    """
    Utility for resolving storage paths.
    """

    def __init__(
        self,
        *,
        root_directory: Path,
    ) -> None:
        self._root_directory = root_directory

    def root(
        self,
    ) -> Path:
        """
        Return the storage root directory.
        """

        return self._root_directory

    def object_directory(
        self,
        *,
        object_id: str,
    ) -> Path:
        """
        Return the storage container directory.

        Example:
            storage/
                conversations/
                    conv_123/
        """

        return self._root_directory / "conversations" / object_id

    def object_file(
        self,
        *,
        object_id: str,
        filename: str,
    ) -> Path:
        """
        Return the object file path.
        """

        return (
            self.object_directory(
                object_id=object_id,
            )
            / filename
        )

    def metadata_file(
        self,
        *,
        object_id: str,
        filename: str,
    ) -> Path:
        """
        Return the metadata file path.
        """

        metadata_name = f"{Path(filename).stem}.metadata.json"

        return (
            self.object_directory(
                object_id=object_id,
            )
            / metadata_name
        )

    def ensure_object_directory(
        self,
        *,
        object_id: str,
    ) -> Path:
        """
        Ensure the storage container directory exists.
        """

        directory = self.object_directory(
            object_id=object_id,
        )

        try:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            log.debug(
                "Storage directory ready: %s",
                directory,
            )

            return directory

        except OSError as exc:
            log.exception(
                "Failed to create storage directory '%s'.",
                directory,
            )

            raise ClientProviderError(
                message="Failed to create storage directory.",
            ) from exc
