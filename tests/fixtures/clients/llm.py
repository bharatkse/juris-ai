"""
Fixtures for provider-independent LLM clients.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.clients.llm.base import LLMClient
from src.clients.models import LLMRequest
from src.core.enums import LLMProvider
from tests.builders.clients.llm import build_llm_request


@pytest.fixture
def mock_llm_client() -> LLMClient:
    """
    Return a mocked provider-independent LLM client.
    """

    client = MagicMock(
        spec=LLMClient,
    )

    client.provider = LLMProvider.GROQ.value
    client.model = "llama-3.3-70b-versatile"

    return client


@pytest.fixture
def llm_request() -> LLMRequest:
    """
    Build a default LLM request.
    """

    return build_llm_request()
