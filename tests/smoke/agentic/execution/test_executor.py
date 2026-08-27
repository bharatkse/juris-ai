"""
Smoke test for the complete execution runtime.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from execution.config import ExecutionRetryPolicy, ExecutionTimeoutPolicy
from execution.executor import Executor
from execution.graph.builder import ExecutionGraphBuilder
from execution.graph.factory import ExecutionGraphFactory
from execution.retry import RetryClassifier
from execution.state import ExecutionStateAssembler
from registry.agent import AgentRegistry

from core.dto.agent import AgentContextDTO, AgentResponseDTO
from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.dto.tool import ToolFileDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, ExecutionStatusEnum, IntentEnum


class SmokeAgent:
    """
    Minimal agent used by the executor smoke test.
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


class SmokeAgentMetadata:
    """
    Metadata required by AgentRegistry.
    """

    name = AgentTypeEnum.LEGAL
    description = "Smoke test legal agent"
    capabilities = ()
    tools = ()


@pytest.mark.asyncio
async def test_executor_smoke() -> None:
    """
    Verify the complete execution runtime from Executor through
    LangGraph and AgentExecutionNode to the registered agent.
    """

    # ------------------------------------------------------------------
    # Agent registry
    # ------------------------------------------------------------------

    agent = SmokeAgent()
    agent.metadata = SmokeAgentMetadata()

    agent_registry = AgentRegistry()

    agent_registry.register(
        component=agent,
    )

    # ------------------------------------------------------------------
    # Execution graph runtime
    # ------------------------------------------------------------------

    graph_factory = ExecutionGraphFactory(
        builder=ExecutionGraphBuilder(),
        agent_registry=agent_registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=3,
        ),
        retry_classifier=RetryClassifier(),
    )

    executor = Executor(
        graph_factory=graph_factory,
        state_assembler=ExecutionStateAssembler(),
        timeout_policy=ExecutionTimeoutPolicy(),
    )

    # ------------------------------------------------------------------
    # Execution plan
    #
    #         step-a
    #         /    \
    #     step-b  step-c
    #         \    /
    #          step-d
    # ------------------------------------------------------------------

    steps = (
        ExecutionStepDTO(
            id="step-a",
            agent=AgentTypeEnum.LEGAL,
            instruction="Execute A",
        ),
        ExecutionStepDTO(
            id="step-b",
            agent=AgentTypeEnum.LEGAL,
            instruction="Execute B",
            depends_on=("step-a",),
        ),
        ExecutionStepDTO(
            id="step-c",
            agent=AgentTypeEnum.LEGAL,
            instruction="Execute C",
            depends_on=("step-a",),
        ),
        ExecutionStepDTO(
            id="step-d",
            agent=AgentTypeEnum.LEGAL,
            instruction="Execute D",
            depends_on=("step-b", "step-c"),
        ),
    )

    plan = ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=steps,
    )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    result = await executor.execute(
        request_id=uuid4(),
        conversation=ConversationDTO(
            messages=(),
        ),
        context=AgentContextDTO(),
        plan=plan,
    )

    # ------------------------------------------------------------------
    # Verify execution state
    # ------------------------------------------------------------------

    assert result.state.status is ExecutionStatusEnum.COMPLETED

    for step_id in (
        "step-a",
        "step-b",
        "step-c",
        "step-d",
    ):
        assert result.state.steps[step_id].status is ExecutionStatusEnum.COMPLETED

    # ------------------------------------------------------------------
    # Verify artifacts
    # ------------------------------------------------------------------

    assert set(result.artifacts) == {
        "step-a.response",
        "step-b.response",
        "step-c.response",
        "step-d.response",
    }

    assert result.artifacts["step-a.response"].content == "Executed: Execute A"

    assert result.artifacts["step-b.response"].content == "Executed: Execute B"

    assert result.artifacts["step-c.response"].content == "Executed: Execute C"

    assert result.artifacts["step-d.response"].content == "Executed: Execute D"

    # ------------------------------------------------------------------
    # Verify agent execution count
    # ------------------------------------------------------------------

    assert len(result.state.steps) == 4
    assert len(result.artifacts) == 4


@pytest.mark.asyncio
async def test_executor_smoke_skips_dependent_step_after_failure() -> None:
    """
    Verify that a failed dependency prevents a dependent step from
    executing and results in a failed execution.
    """

    class FailingSmokeAgent:
        """
        Minimal agent that always fails.
        """

        async def run(
            self,
            *,
            request,
        ) -> AgentResponseDTO:
            if request.instruction == "Execute A":
                raise RuntimeError("Simulated agent failure.")

            return AgentResponseDTO(
                content=f"Executed: {request.instruction}",
                agent_name="legal",
            )

    agent = FailingSmokeAgent()

    agent.metadata = SmokeAgentMetadata()

    agent_registry = AgentRegistry()

    agent_registry.register(
        component=agent,
    )

    graph_factory = ExecutionGraphFactory(
        builder=ExecutionGraphBuilder(),
        agent_registry=agent_registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=1,
        ),
        retry_classifier=RetryClassifier(),
    )

    executor = Executor(
        graph_factory=graph_factory,
        state_assembler=ExecutionStateAssembler(),
        timeout_policy=ExecutionTimeoutPolicy(),
    )

    plan = ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepDTO(
                id="step-a",
                agent=AgentTypeEnum.LEGAL,
                instruction="Execute A",
            ),
            ExecutionStepDTO(
                id="step-b",
                agent=AgentTypeEnum.LEGAL,
                instruction="Execute B",
                depends_on=("step-a",),
            ),
        ),
    )

    result = await executor.execute(
        request_id=uuid4(),
        conversation=ConversationDTO(
            messages=(),
        ),
        context=AgentContextDTO(),
        plan=plan,
    )

    assert result.state.status is ExecutionStatusEnum.FAILED

    assert result.state.steps["step-a"].status is ExecutionStatusEnum.FAILED

    assert result.state.steps["step-b"].status is ExecutionStatusEnum.SKIPPED

    assert result.state.steps["step-a"].error == "Simulated agent failure."

    assert result.state.steps["step-b"].error == (
        "Step skipped because one or more " "dependencies did not complete successfully."
    )

    assert "step-a.response" not in result.artifacts
    assert "step-b.response" not in result.artifacts


@pytest.mark.asyncio
async def test_executor_smoke_preserves_uploaded_file_context() -> None:
    """
    Verify that uploaded files in the agent context are preserved
    through the complete execution runtime and reach the agent.
    """

    uploaded_file = ToolFileDTO(
        filename="contract.pdf",
        content=b"contract content",
        content_type="application/pdf",
    )

    context = AgentContextDTO(
        uploaded_files=(uploaded_file,),
    )

    class ContextSmokeAgent:
        """
        Minimal agent that captures the execution context.
        """

        def __init__(self) -> None:
            self.metadata = SmokeAgentMetadata()
            self.received_context: AgentContextDTO | None = None

        async def run(
            self,
            *,
            request,
        ) -> AgentResponseDTO:
            self.received_context = request.context

            return AgentResponseDTO(
                content="Document context received.",
                agent_name="legal",
            )

    agent = ContextSmokeAgent()

    agent_registry = AgentRegistry()

    agent_registry.register(
        component=agent,
    )

    graph_factory = ExecutionGraphFactory(
        builder=ExecutionGraphBuilder(),
        agent_registry=agent_registry,
        retry_policy=ExecutionRetryPolicy(
            max_attempts=1,
        ),
        retry_classifier=RetryClassifier(),
    )

    executor = Executor(
        graph_factory=graph_factory,
        state_assembler=ExecutionStateAssembler(),
        timeout_policy=ExecutionTimeoutPolicy(),
    )

    plan = ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepDTO(
                id="document-step",
                agent=AgentTypeEnum.LEGAL,
                instruction="Answer the question using the uploaded document.",
            ),
        ),
    )

    result = await executor.execute(
        request_id=uuid4(),
        conversation=ConversationDTO(
            messages=(),
        ),
        context=context,
        plan=plan,
    )

    assert result.state.status is ExecutionStatusEnum.COMPLETED

    assert result.state.steps["document-step"].status is ExecutionStatusEnum.COMPLETED

    assert agent.received_context is context

    assert agent.received_context.uploaded_files == (uploaded_file,)

    assert agent.received_context.uploaded_files[0].filename == "contract.pdf"

    assert agent.received_context.uploaded_files[0].content == b"contract content"

    assert agent.received_context.uploaded_files[0].content_type == "application/pdf"

    assert result.artifacts["document-step.response"].content == "Document context received."
