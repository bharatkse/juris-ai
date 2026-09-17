import asyncio

import pytest

from agentic.registry.tool import ToolRegistry
from agentic.tools.base import Tool
from agentic.tools.runtime.invocation import ToolExecutionService


class ConcurrentTool(Tool):
    name = "concurrent"
    description = "Test tool."

    async def execute(
        self,
        *,
        request_id: str,
    ) -> str:
        await asyncio.sleep(0)

        return request_id


@pytest.mark.asyncio
async def test_tool_execution_is_concurrent_and_isolated() -> None:
    registry = ToolRegistry()
    registry.register(component=ConcurrentTool())

    service = ToolExecutionService(
        tool_registry=registry,
    )

    results = await asyncio.gather(
        service.execute(
            tool_name="concurrent",
            parameters={"request_id": "request-a"},
        ),
        service.execute(
            tool_name="concurrent",
            parameters={"request_id": "request-b"},
        ),
    )

    assert results[0].success is True
    assert results[0].content == "request-a"

    assert results[1].success is True
    assert results[1].content == "request-b"
