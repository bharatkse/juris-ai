"""
Execution runtime session.

Owns the mutable runtime state for a single execution request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.agents.models import AgentContext, AgentRequest
from src.core.exceptions.execution import ExecutionError
from src.core.models.conversation import Conversation
from src.core.models.planning import ExecutionMode, ExecutionPlan, ExecutionStep
from src.execution.bus import CollaborationBus
from src.execution.hybrid import HybridExecutionStrategy
from src.execution.memory import ExecutionMemory
from src.execution.parallel import ParallelExecutionStrategy
from src.execution.protocols import ExecutionStrategy
from src.execution.sequential import SequentialExecutionStrategy
from src.execution.state import ExecutionState, ExecutionStatus
from src.registry.agent import AgentRegistry

if TYPE_CHECKING:
    from src.execution.result import ExecutionResult


class ExecutionSession:
    """
    Runtime execution session.

    Each execution request owns its own session.
    """

    def __init__(
        self,
        *,
        request_id: UUID,
        conversation: Conversation,
        plan: ExecutionPlan,
        agent_registry: AgentRegistry,
        sequential_strategy: SequentialExecutionStrategy,
        parallel_strategy: ParallelExecutionStrategy,
        hybrid_strategy: HybridExecutionStrategy,
    ) -> None:
        self._plan = plan
        self._conversation = conversation

        self._agent_registry = agent_registry

        self._sequential_strategy = sequential_strategy
        self._parallel_strategy = parallel_strategy
        self._hybrid_strategy = hybrid_strategy

        self._state = ExecutionState(
            request_id=request_id,
            status=ExecutionStatus.RUNNING,
        )

        for step in plan.steps:
            self._state.register_step(
                step_id=step.id,
            )

        self._memory = ExecutionMemory()
        self._bus = CollaborationBus()

    async def execute(
        self,
    ) -> ExecutionResult:
        """
        Execute the execution plan.
        """

        strategy = self._resolve_strategy(
            mode=self._plan.mode,
        )

        try:
            await strategy.execute(
                plan=self._plan,
                step_runner=self._run_step,
            )

            self._state.status = ExecutionStatus.COMPLETED

        except Exception:
            self._state.status = ExecutionStatus.FAILED
            raise

        return ExecutionResult(
            state=self._state,
            artifacts=dict(
                self._memory.artifacts,
            ),
        )

    async def _run_step(
        self,
        *,
        step: ExecutionStep,
    ) -> None:
        """
        Execute a single execution step.
        """

        self._state.start_step(
            step_id=step.id,
        )

        try:
            agent = self._agent_registry.resolve(
                key=step.agent.value,
            )

            response = await agent.execute(
                request=self._build_agent_request(
                    step=step,
                ),
            )

            self._memory.put_artifact(
                key=f"{step.id}.response",
                value=response,
            )

            self._state.complete_step(
                step_id=step.id,
            )

        except Exception as exc:
            self._state.fail_step(
                step_id=step.id,
                error=str(exc),
            )
            raise

    def _build_agent_request(
        self,
        *,
        step: ExecutionStep,
    ) -> AgentRequest:
        """
        Build the request for an execution agent.
        """

        return AgentRequest(
            conversation=self._conversation,
            context=AgentContext(
                instruction=step.instruction,
            ),
        )

    def _resolve_strategy(
        self,
        *,
        mode: ExecutionMode,
    ) -> ExecutionStrategy:
        """
        Resolve the execution strategy.
        """

        match mode:
            case ExecutionMode.SEQUENTIAL:
                return self._sequential_strategy

            case ExecutionMode.PARALLEL:
                return self._parallel_strategy

            case ExecutionMode.HYBRID:
                return self._hybrid_strategy

            case _:
                raise ExecutionError(
                    message=(f"Unsupported execution mode '{mode.value}'."),
                )
