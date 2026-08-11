"""
Execution runtime session.

Owns the mutable runtime state for a single execution request.
"""

from __future__ import annotations

from uuid import UUID

from src.core.dto.agent import AgentRequestDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from src.core.enums import ExecutionModeEnum, ExecutionStatusEnum
from src.core.exceptions.execution import ExecutionError
from src.core.logger import get_logger
from src.execution.bus import CollaborationBus
from src.execution.hybrid import HybridExecutionStrategy
from src.execution.parallel import ParallelExecutionStrategy
from src.execution.protocols import ExecutionStrategy
from src.execution.schemas.memory import ExecutionMemorySchema
from src.execution.schemas.result import ExecutionResultSchema
from src.execution.schemas.state import ExecutionStateSchema
from src.execution.sequential import SequentialExecutionStrategy
from src.registry.agent import AgentRegistry

logger = get_logger(__name__)


class ExecutionSession:
    """
    Runtime execution session.

    Each execution request owns its own session.
    """

    def __init__(
        self,
        *,
        request_id: UUID,
        conversation: ConversationDTO,
        plan: ExecutionPlanDTO,
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

        self._state = ExecutionStateSchema(
            request_id=request_id,
            status=ExecutionStatusEnum.RUNNING,
        )

        for step in plan.steps:
            self._state.register_step(
                step_id=step.id,
            )

        self._memory = ExecutionMemorySchema()
        self._bus = CollaborationBus()

    async def execute(
        self,
    ) -> ExecutionResultSchema:
        """
        Execute the execution plan.
        """

        logger.info(
            "Starting execution session.",
            extra={
                "operation": "execute_session",
                "request_id": str(self._state.request_id),
                "execution_mode": self._plan.mode.value,
                "step_count": len(self._plan.steps),
            },
        )

        strategy = self._resolve_strategy(
            mode=self._plan.mode,
        )

        try:
            await strategy.execute(
                plan=self._plan,
                step_runner=self._run_step,
            )

            self._state.status = ExecutionStatusEnum.COMPLETED

            logger.info(
                "Execution session completed.",
                extra={
                    "operation": "execute_session",
                    "request_id": str(self._state.request_id),
                    "execution_mode": self._plan.mode.value,
                },
            )

        except Exception:
            self._state.status = ExecutionStatusEnum.FAILED

            logger.exception(
                "Execution session failed.",
                extra={
                    "operation": "execute_session",
                    "request_id": str(self._state.request_id),
                    "execution_mode": self._plan.mode.value,
                },
            )

            raise

        return ExecutionResultSchema(
            state=self._state,
            artifacts=dict(
                self._memory.artifacts,
            ),
        )

    async def _run_step(
        self,
        *,
        step: ExecutionStepDTO,
    ) -> None:
        """
        Execute a single execution step.
        """

        logger.info(
            "Starting execution step.",
            extra={
                "operation": "execute_step",
                "request_id": str(self._state.request_id),
                "step_id": step.id,
                "agent": step.agent.value,
            },
        )

        self._state.start_step(
            step_id=step.id,
        )

        try:
            agent = self._agent_registry.resolve(
                key=step.agent.value,
            )

            logger.debug(
                "Resolved execution agent.",
                extra={
                    "operation": "resolve_agent",
                    "request_id": str(self._state.request_id),
                    "step_id": step.id,
                    "agent": step.agent.value,
                },
            )

            response = await agent.run(
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

            logger.info(
                "Execution step completed.",
                extra={
                    "operation": "execute_step",
                    "request_id": str(self._state.request_id),
                    "step_id": step.id,
                    "agent": step.agent.value,
                },
            )

        except Exception as exc:
            self._state.fail_step(
                step_id=step.id,
                error=str(exc),
            )

            logger.exception(
                "Execution step failed.",
                extra={
                    "operation": "execute_step",
                    "request_id": str(self._state.request_id),
                    "step_id": step.id,
                    "agent": step.agent.value,
                },
            )

            # raise

    def _build_agent_request(
        self,
        *,
        step: ExecutionStepDTO,
    ) -> AgentRequestDTO:
        """
        Build the request for an execution agent.
        """

        return AgentRequestDTO(
            conversation=self._conversation,
            instruction=step.instruction,
        )

    def _resolve_strategy(
        self,
        *,
        mode: ExecutionModeEnum,
    ) -> ExecutionStrategy:
        """
        Resolve the execution strategy.
        """

        match mode:
            case ExecutionModeEnum.SEQUENTIAL:
                return self._sequential_strategy

            case ExecutionModeEnum.PARALLEL:
                return self._parallel_strategy

            case ExecutionModeEnum.HYBRID:
                return self._hybrid_strategy

            case _:
                raise ExecutionError(
                    message=(f"Unsupported execution mode '{mode.value}'."),
                )
