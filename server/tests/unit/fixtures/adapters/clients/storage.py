"""
Client fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from adapters.clients.storage.base import StorageClient
from core.enums import StorageTypeEnum


@pytest.fixture
def mock_storage_client() -> StorageClient:
    """
    Return a mocked storage client.
    """

    client = AsyncMock(
        spec=StorageClient,
    )

    client.storage_type = StorageTypeEnum.LOCAL

    return client
