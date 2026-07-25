"""
Fixtures for Groq client tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.clients.groq import GroqClient


@pytest.fixture
def mock_groq_sdk() -> MagicMock:
    """
    Mock Groq SDK client.
    """

    sdk = MagicMock()

    sdk.chat.completions.create = AsyncMock()

    return sdk


@pytest.fixture
def groq_client(
    mock_groq_sdk: MagicMock,
) -> GroqClient:
    """
    Create a Groq client backed by a mocked SDK.
    """

    with patch(
        "src.clients.groq.AsyncGroq",
        return_value=mock_groq_sdk,
    ):
        return GroqClient()


@pytest.fixture
def mock_chat_completion(
    mock_groq_sdk: MagicMock,
) -> AsyncMock:
    """
    Mock Groq chat completion endpoint.
    """

    return mock_groq_sdk.chat.completions.create
