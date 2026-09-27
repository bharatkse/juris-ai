import asyncio

import pytest

from agentic.registry.tool import ToolRegistry
from agentic.tools.base import Tool
from agentic.tools.runtime.invocation import ToolExecutionService
from core.dto.clients.search_engine import SearchEngineResultDTO


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


class StrictQueryTool(Tool):
    name = "strict_query"
    description = "Accepts only query."

    async def execute(self, *, query: str) -> str:
        return query


class BoomTool(Tool):
    name = "boom"
    description = "Raises."

    async def execute(self, *, query: str) -> str:
        raise TypeError("unexpected keyword argument 'engine'")


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


@pytest.mark.asyncio
async def test_unknown_tool_parameters_are_dropped() -> None:
    registry = ToolRegistry()
    registry.register(component=StrictQueryTool())
    service = ToolExecutionService(tool_registry=registry)

    result = await service.execute(
        tool_name="strict_query",
        parameters={"query": "alimony", "num_results": 5, "search_type": "web"},
    )

    assert result.success is True
    assert result.content == "alimony"


@pytest.mark.asyncio
async def test_tool_exception_becomes_failed_result() -> None:
    registry = ToolRegistry()
    registry.register(component=BoomTool())
    service = ToolExecutionService(tool_registry=registry)

    result = await service.execute(
        tool_name="boom",
        parameters={"query": "alimony"},
    )

    assert result.success is False
    assert "engine" in (result.error or "")


def test_search_engine_result_accepts_engine() -> None:
    result = SearchEngineResultDTO(
        title="Habeas corpus - Wikipedia",
        url="https://en.wikipedia.org/wiki/Habeas_corpus",
        snippet="A legal procedure.",
        engine="google",
    )

    assert result.engine == "google"
