"""
Unit tests for agent execution node.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.execution.config import ExecutionRetryPolicy
from agentic.execution.graph.nodes import AgentExecutionNode
from agentic.execution.retry import RetryClassifier
from agentic.registry.agent import AgentRegistry
from core.dto.agent import AgentMetadataDTO, AgentResponseDTO
from core.dto.tool import ToolFileDTO
from core.enums import ExecutionStatusEnum
from tests.builders.agentic.agent import build_agent_context
from tests.builders.agentic.execution import build_graph_state
from tests.builders.agentic.planning import build_plan, build_step


@pytest.mark.asyncio
async def test_execute_step_successfully() -> None:
    """
    It should resolve the agent, execute it, and produce completed
    execution and response-artifact updates.
    """

    step = build_step("step-a")

    response = AgentResponseDTO(
        agent_name="legal",
        content="Executed A",
    )

    agent = MagicMock()

    agent.metadata = AgentMetadataDTO(
        name="legal",
        description="Legal agent.",
        capabilities=("legal",),
    )
    agent.run = AsyncMock(
        return_value=response,
    )

    registry = AgentRegistry()

    registry.register(
        component=agent,
    )

    node = AgentExecutionNode(
        agent_registry=registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(),
    )

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(step,),
        ),
    )

    result = await node(
        graph_state,
        step=step,
    )

    assert len(result["execution_state_updates"]) == 1

    update = result["execution_state_updates"][0]

    assert update["step_id"] == "step-a"
    assert update["status"] is ExecutionStatusEnum.COMPLETED
    assert update["retry_count"] == 0
    assert update["started_at"] is not None
    assert update["completed_at"] is not None
    assert update["error"] is None

    assert len(result["memory_updates"]) == 1

    artifact = result["memory_updates"][0]

    assert artifact["key"] == "step-a.response"
    assert artifact["value"] == response

    agent.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_step_fails_without_retry_for_non_retryable_error() -> None:
    """
    It should fail immediately when the agent raises a non-retryable
    exception.
        ```
        attempt 1 → failure
        attempt 2 → success
        retry_count = 1
        ```
    """

    step = build_step("step-a")

    agent = MagicMock()

    agent.metadata = AgentMetadataDTO(
        name="legal",
        description="Legal agent.",
        capabilities=("legal",),
    )

    agent.run = AsyncMock(
        side_effect=RuntimeError("Non-retryable failure"),
    )

    registry = AgentRegistry()

    registry.register(
        component=agent,
    )

    node = AgentExecutionNode(
        agent_registry=registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(),
    )

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(step,),
        ),
    )

    result = await node(
        graph_state,
        step=step,
    )

    assert (
        len(
            result["execution_state_updates"],
        )
        == 1
    )

    update = result["execution_state_updates"][0]

    assert update["step_id"] == "step-a"
    assert update["status"] is ExecutionStatusEnum.FAILED
    assert update["retry_count"] == 0
    assert update["started_at"] is not None
    assert update["completed_at"] is not None
    assert update["error"] == "Non-retryable failure"

    assert (
        result.get(
            "memory_updates",
            [],
        )
        == []
    )

    agent.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_step_retries_retryable_error_and_succeeds() -> None:
    """
    It should retry a retryable failure and complete successfully.
        ```
        attempt 1 → failure
        attempt 2 → failure
        attempt 3 → failure

        FAILED
        retry_count = 2
        ```
    """

    step = build_step("step-a")

    response = AgentResponseDTO(
        agent_name="legal",
        content="Executed A",
    )

    agent = MagicMock()

    agent.metadata = AgentMetadataDTO(
        name="legal",
        description="Legal agent.",
        capabilities=("legal",),
    )

    agent.run = AsyncMock(
        side_effect=[
            TimeoutError("Temporary timeout"),
            response,
        ],
    )

    registry = AgentRegistry()

    registry.register(
        component=agent,
    )

    node = AgentExecutionNode(
        agent_registry=registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(
            retryable_exceptions=(TimeoutError,),
        ),
    )

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(step,),
        ),
    )

    result = await node(
        graph_state,
        step=step,
    )

    assert (
        len(
            result["execution_state_updates"],
        )
        == 1
    )

    update = result["execution_state_updates"][0]

    assert update["step_id"] == "step-a"
    assert update["status"] is ExecutionStatusEnum.COMPLETED
    assert update["retry_count"] == 1
    assert update["started_at"] is not None
    assert update["completed_at"] is not None
    assert update["error"] is None

    assert (
        len(
            result["memory_updates"],
        )
        == 1
    )

    artifact = result["memory_updates"][0]

    assert artifact["key"] == "step-a.response"
    assert artifact["value"] == response

    assert agent.run.await_count == 2


@pytest.mark.asyncio
async def test_execute_step_fails_after_retryable_error_exhausts_attempts() -> None:
    """
    It should fail after all retry attempts are exhausted.
    ```
        success
        └── attempt 1 → COMPLETED, retry_count=0

        non-retryable failure
        └── attempt 1 → FAILED, retry_count=0

        retryable → success
        └── attempt 1 → failure
        └── attempt 2 → COMPLETED, retry_count=1

        retryable → exhausted
        └── attempt 1 → failure
        └── attempt 2 → failure
        └── attempt 3 → FAILED, retry_count=2
        ```
    """

    step = build_step("step-a")

    agent = MagicMock()

    agent.metadata = AgentMetadataDTO(
        name="legal",
        description="Legal agent.",
        capabilities=("legal",),
    )

    agent.run = AsyncMock(
        side_effect=TimeoutError("Persistent timeout"),
    )

    registry = AgentRegistry()

    registry.register(
        component=agent,
    )

    node = AgentExecutionNode(
        agent_registry=registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(
            retryable_exceptions=(TimeoutError,),
        ),
    )

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(step,),
        ),
    )

    result = await node(
        graph_state,
        step=step,
    )

    assert (
        len(
            result["execution_state_updates"],
        )
        == 1
    )

    update = result["execution_state_updates"][0]

    assert update["step_id"] == "step-a"
    assert update["status"] is ExecutionStatusEnum.FAILED

    # 3 attempts = 2 actual retries.
    assert update["retry_count"] == 2

    assert update["started_at"] is not None
    assert update["completed_at"] is not None
    assert update["error"] == "Persistent timeout"

    assert (
        result.get(
            "memory_updates",
            [],
        )
        == []
    )

    assert agent.run.await_count == 3


@pytest.mark.asyncio
async def test_execute_step_fails_when_agent_is_not_registered() -> None:
    """
    It should fail the execution step when the requested agent
    cannot be resolved from the registry.
    ```
        AgentRegistry.resolve()
                ↓
        AgentNotFoundError
                ↓
        AgentExecutionNode
                ↓
        FAILED execution update
    ```
    """

    step = build_step("step-a")

    registry = AgentRegistry()

    node = AgentExecutionNode(
        agent_registry=registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(),
    )

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(step,),
        ),
    )

    result = await node(
        graph_state,
        step=step,
    )

    assert (
        len(
            result["execution_state_updates"],
        )
        == 1
    )

    update = result["execution_state_updates"][0]

    assert update["step_id"] == "step-a"
    assert update["status"] is ExecutionStatusEnum.FAILED
    assert update["retry_count"] == 0
    assert update["started_at"] is not None
    assert update["completed_at"] is not None
    assert update["error"] is not None

    assert "No agent registered" in update["error"]

    assert (
        result.get(
            "memory_updates",
            [],
        )
        == []
    )


@pytest.mark.asyncio
async def test_execute_step_passes_request_context_to_agent() -> None:
    """
    It should pass conversation, instruction, arguments, and runtime
    context to the agent.
        ```
        ChatRequest.files
            ↓
        build_tool_files()
            ↓
        AgentContextDTO.uploaded_files
            ↓
        ExecutionGraphState.context
            ↓
        AgentRequestDTO.context
            ↓
        BaseAgent
            ↓
        RetrieverTool
        ```
    """

    step = build_step("step-a")

    uploaded_file = ToolFileDTO(
        filename="contract.pdf",
        content=b"contract content",
        content_type="application/pdf",
    )

    context = build_agent_context(
        uploaded_files=(uploaded_file,),
        metadata={
            "source": "chat",
        },
    )

    response = AgentResponseDTO(
        agent_name="legal",
        content="Executed A",
    )

    agent = MagicMock()

    agent.metadata = AgentMetadataDTO(
        name="legal",
        description="Legal agent.",
        capabilities=("legal",),
    )

    agent.run = AsyncMock(
        return_value=response,
    )

    registry = AgentRegistry()

    registry.register(
        component=agent,
    )

    node = AgentExecutionNode(
        agent_registry=registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(),
    )

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(step,),
        ),
        context=context,
    )

    await node(
        graph_state,
        step=step,
    )

    agent.run.assert_awaited_once()

    request = agent.run.await_args.kwargs["request"]

    assert request.conversation == graph_state["conversation"]
    assert request.instruction == step.instruction
    assert request.arguments == step.arguments

    assert request.context is context
    assert request.context.uploaded_files == (uploaded_file,)
    assert request.context.metadata == {
        "source": "chat",
    }
