"""
Retry smoke tests for the LangGraph agent execution node.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.dto.agent import AgentContextDTO, AgentResponseDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from src.core.enums import AgentTypeEnum, ExecutionModeEnum, ExecutionStatusEnum
from src.execution.config import ExecutionRetryPolicy
from src.execution.graph.nodes import AgentExecutionNode
from src.execution.graph.state import ExecutionGraphState
from src.execution.retry import RetryClassifier


class RetryableError(Exception):
    """Test retryable failure."""


@pytest.mark.asyncio
async def test_agent_execution_node_smoke() -> None:
    """
    Verify that a root execution step completes successfully.
    """

    class FakeAgent:
        """
        Minimal agent used by the smoke test.
        """

        async def run(
            self,
            *,
            request,
        ) -> AgentResponseDTO:
            return AgentResponseDTO(
                content=f"Executed: {request.instruction}",
                agent_name="legal",
            )

    class FakeAgentRegistry:
        """
        Minimal registry used by the smoke test.
        """

        def __init__(
            self,
            agent: FakeAgent,
        ) -> None:
            self._agent = agent

        def resolve(
            self,
            *,
            key: str,
        ) -> FakeAgent:
            assert key == AgentTypeEnum.LEGAL

            return self._agent

    step = ExecutionStepDTO(
        id="step-a",
        agent=AgentTypeEnum.LEGAL,
        instruction="Execute A",
    )

    plan = ExecutionPlanDTO(
        intent="Smoke test",
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(step,),
    )

    state: ExecutionGraphState = {
        "request_id": uuid4(),
        "conversation": ConversationDTO(
            messages=(),
        ),
        "context": AgentContextDTO(),
        "plan": plan,
        "execution_state_updates": [],
        "memory_updates": [],
    }

    node = AgentExecutionNode(
        agent_registry=FakeAgentRegistry(
            FakeAgent(),
        ),
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(),
    )

    result = await node(
        state,
        step=step,
    )

    execution_updates = result["execution_state_updates"]
    memory_updates = result["memory_updates"]

    assert len(execution_updates) == 1

    execution_update = execution_updates[0]

    assert execution_update["step_id"] == "step-a"
    assert execution_update["status"] is ExecutionStatusEnum.COMPLETED
    assert execution_update["retry_count"] == 0
    assert execution_update["error"] is None

    assert len(memory_updates) == 1

    memory_update = memory_updates[0]

    assert memory_update["key"] == "step-a.response"

    response = memory_update["value"]

    assert isinstance(response, AgentResponseDTO)
    assert response.content == "Executed: Execute A"

    print("Agent execution node smoke test passed")
    print(f"Step status: {execution_update['status'].value}")
    print(f"Retry count: {execution_update['retry_count']}")
    print(f"Artifact: {memory_update['key']}")


@pytest.mark.asyncio
async def test_agent_execution_node_retries_then_succeeds() -> None:
    """
    Verify that a retryable failure is retried and eventually succeeds.
    """

    class FlakyAgent:
        """
        Fails once and succeeds on the second attempt.
        """

        def __init__(self) -> None:
            self.attempts = 0

        async def run(
            self,
            *,
            request,
        ) -> AgentResponseDTO:
            self.attempts += 1

            if self.attempts == 1:
                raise RetryableError(
                    "Temporary agent failure.",
                )

            return AgentResponseDTO(
                content=f"Executed: {request.instruction}",
                agent_name="legal",
            )

    class FakeAgentRegistry:
        """
        Minimal registry for the retry smoke test.
        """

        def __init__(
            self,
            agent: FlakyAgent,
        ) -> None:
            self._agent = agent

        def resolve(
            self,
            *,
            key: str,
        ) -> FlakyAgent:
            assert key == AgentTypeEnum.LEGAL

            return self._agent

    step = ExecutionStepDTO(
        id="step-a",
        agent=AgentTypeEnum.LEGAL,
        instruction="Execute A",
    )

    plan = ExecutionPlanDTO(
        intent="Retry smoke test",
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(step,),
    )

    state: ExecutionGraphState = {
        "request_id": uuid4(),
        "conversation": ConversationDTO(
            messages=(),
        ),
        "context": AgentContextDTO(),
        "plan": plan,
        "execution_state_updates": [],
        "memory_updates": [],
    }

    agent = FlakyAgent()

    node = AgentExecutionNode(
        agent_registry=FakeAgentRegistry(
            agent,
        ),
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(
            retryable_exceptions=(RetryableError,),
        ),
    )

    result = await node(
        state,
        step=step,
    )

    execution_updates = result["execution_state_updates"]
    memory_updates = result["memory_updates"]

    assert agent.attempts == 2

    assert len(execution_updates) == 1

    execution_update = execution_updates[0]

    assert execution_update["step_id"] == "step-a"
    assert execution_update["status"] is ExecutionStatusEnum.COMPLETED
    assert execution_update["retry_count"] == 1
    assert execution_update["error"] is None

    assert len(memory_updates) == 1

    memory_update = memory_updates[0]

    assert memory_update["key"] == "step-a.response"
    assert memory_update["value"].content == "Executed: Execute A"

    print("Retry smoke test passed")
    print(f"Attempts: {agent.attempts}")
    print(f"Retry count: {execution_update['retry_count']}")
    print(f"Step status: {execution_update['status'].value}")
