"""
Client fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.clients.storage.base import StorageClient
from src.core.enums import StorageType


@pytest.fixture
def mock_storage_client() -> StorageClient:
    """
    Return a mocked storage client.
    """

    client = AsyncMock(
        spec=StorageClient,
    )

    client.storage_type = StorageType.LOCAL

    return client
