"""
Storage metadata serializer.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from src.clients.storage.models import StoredObject
from src.core.exceptions_.client import ClientProviderError


class StorageSerializer:
    """
    Serialize and deserialize storage metadata.
    """

    @classmethod
    def dumps(cls, stored_object: StoredObject, *, indent: int | None = None) -> str:
        """
        Serialize a stored object into JSON.
        """

        return json.dumps(
            cls.serialize(
                stored_object,
            ),
            indent=indent,
        )

    @classmethod
    def loads(
        cls,
        payload: str,
    ) -> StoredObject:
        """
        Deserialize a stored object from JSON.
        """

        try:
            metadata = json.loads(
                payload,
            )

        except json.JSONDecodeError as exc:
            raise ClientProviderError(
                message="Failed to deserialize storage metadata.",
            ) from exc

        return cls.deserialize(
            metadata,
        )

    @staticmethod
    def serialize(
        stored_object: StoredObject,
    ) -> dict[str, Any]:
        """
        Serialize a stored object into a dictionary.
        """

        return {
            "object_id": stored_object.object_id,
            "filename": stored_object.filename,
            "content_type": stored_object.content_type,
            "size": stored_object.size,
            "checksum": stored_object.checksum,
            "storage_path": stored_object.storage_path,
            "created_at": stored_object.created_at.isoformat(),
            "metadata": stored_object.metadata,
        }

    @staticmethod
    def deserialize(
        payload: dict[str, Any],
    ) -> StoredObject:
        """
        Deserialize a stored object from a dictionary.
        """

        try:
            return StoredObject(
                object_id=payload["object_id"],
                filename=payload["filename"],
                content_type=payload["content_type"],
                size=payload["size"],
                checksum=payload.get(
                    "checksum",
                ),
                storage_path=payload.get(
                    "storage_path",
                ),
                created_at=datetime.fromisoformat(
                    payload["created_at"],
                ),
                metadata=payload.get(
                    "metadata",
                    {},
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ClientProviderError(
                message="Storage metadata is invalid.",
            ) from exc
