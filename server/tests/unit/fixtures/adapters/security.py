"""
Security fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from adapters.security.password import PasswordService


@pytest.fixture
def mock_password_service() -> MagicMock:
    """
    Return a mocked password service.
    """

    service = MagicMock(
        spec=PasswordService,
    )

    service.hash.return_value = "hashed-password"

    return service
