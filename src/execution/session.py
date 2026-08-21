"""
Execution runtime session.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from src.core.dto.agent import AgentContextDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO
from src.core.exceptions.execution import ExecutionError
from src.core.logger import get_logger
from src.execution.config import ExecutionTimeoutPolicy
from src.execution.graph.factory import ExecutionGraphFactory
from src.execution.graph.state import ExecutionGraphState
from src.execution.schemas.result import ExecutionResultSchema
from src.execution.state.assembler import ExecutionStateAssembler

logger = get_logger(__name__)


class ExecutionSession:
    """
    Runtime execution session.

    Owns request-scoped execution context while LangGraph owns
    mutable graph runtime state.
    """

    def __init__(
        self,
        *,
        request_id: UUID,
        conversation: ConversationDTO,
        plan: ExecutionPlanDTO,
        context: AgentContextDTO,
        graph_factory: ExecutionGraphFactory,
        state_assembler: ExecutionStateAssembler,
        timeout_policy: ExecutionTimeoutPolicy,
    ) -> None:
        self._request_id = request_id
        self._conversation = conversation
        self._plan = plan
        self._context = context

        self._graph_factory = graph_factory
        self._state_assembler = state_assembler
        self._timeout_policy = timeout_policy

    async def execute(
        self,
    ) -> ExecutionResultSchema:
        """
        Execute the session through the compiled LangGraph workflow.
        """

        logger.info(
            "Starting execution session.",
            extra={
                "operation": "execute_session",
                "request_id": str(self._request_id),
                "execution_mode": self._plan.mode.value,
                "step_count": len(self._plan.steps),
            },
        )

        try:
            graph = self._graph_factory.create(
                plan=self._plan,
            )

            initial_state = self._build_initial_state()

            graph_state = await asyncio.wait_for(
                graph.ainvoke(
                    initial_state,
                ),
                timeout=self._timeout_policy.timeout_seconds,
            )

            state = self._state_assembler.assemble_state(
                graph_state=graph_state,
            )

            memory = self._state_assembler.assemble_memory(
                graph_state=graph_state,
            )

            action = self._state_assembler.assemble_action(
                graph_state=graph_state,
            )

            logger.info(
                "Execution session completed.",
                extra={
                    "operation": "execute_session",
                    "request_id": str(self._request_id),
                    "execution_status": state.status.value,
                    "execution_mode": self._plan.mode.value,
                },
            )

            return ExecutionResultSchema(
                state=state,
                artifacts=dict(
                    memory.artifacts,
                ),
                action=action,
            )

        except TimeoutError as exc:
            logger.error(
                "Execution session timed out.",
                extra={
                    "operation": "execute_session_timeout",
                    "request_id": str(self._request_id),
                    "execution_mode": self._plan.mode.value,
                    "timeout_seconds": (self._timeout_policy.timeout_seconds),
                },
            )

            raise ExecutionError(
                message=(
                    "Execution timed out after " f"{self._timeout_policy.timeout_seconds} seconds."
                ),
            ) from exc

        except Exception:
            logger.exception(
                "Execution session failed.",
                extra={
                    "operation": "execute_session",
                    "request_id": str(self._request_id),
                    "execution_mode": self._plan.mode.value,
                },
            )

            raise

    def _build_initial_state(self) -> ExecutionGraphState:
        """
        Build the initial LangGraph state.
        """

        return {
            "request_id": self._request_id,
            "conversation": self._conversation,
            "plan": self._plan,
            "context": self._context,
            "execution_state_updates": [],
            "memory_updates": [],
            "action": None,
        }
