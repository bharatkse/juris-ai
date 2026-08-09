"""
Fixtures for Groq client tests.
"""

from __future__ import annotations

import pytest

from src.clients.models import LLMMessage, LLMRequest
from src.core.enums import MessageRole


@pytest.fixture
def llm_request() -> LLMRequest:
    return LLMRequest(
        messages=(
            LLMMessage(
                role=MessageRole.USER,
                content="Hello",
            ),
        ),
        temperature=0.8,
        max_tokens=512,
    )
