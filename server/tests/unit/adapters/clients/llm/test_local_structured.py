"""
LocalLLMClient structured calls: the request's schema goes to Ollama as
``format`` (decoded against, review A19), and ``tools`` is never sent.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.clients.llm.local import LocalLLMClient
from agentic.decisions.schemas import AgentDecision, decision_json_schema
from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.enums import MessageRoleEnum


@pytest.mark.asyncio
async def test_the_decision_schema_is_sent_as_format_and_tools_never_are() -> None:
    client = LocalLLMClient(base_url="http://ollama:11434", model="qwen3:8b")
    client._client.chat = AsyncMock(
        return_value=SimpleNamespace(
            message=SimpleNamespace(content='{"decision_type": "final", "final_response": "ok"}'),
            prompt_eval_count=1,
            eval_count=1,
            done_reason="stop",
        ),
    )
    schema = decision_json_schema(tool_names=["retriever"])

    await client.generate_structured(
        request=LLMRequestDTO(
            messages=(LLMMessageDTO(role=MessageRoleEnum.USER, content="Hi"),),
            response_schema=schema,
        ),
        response_model=AgentDecision,
    )

    kwargs = client._client.chat.await_args.kwargs
    assert kwargs["format"] == schema
    assert "tools" not in kwargs
