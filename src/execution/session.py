"""
Execution runtime session.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from src.core.dto.agent import AgentContextDTO
from src.core.dto.agent_action import AgentActionRequestDTO
from src.core.dto.approval import ApprovalResponseDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO
from src.core.exceptions.execution import ExecutionError
from src.core.logger import get_logger
from src.execution.schemas.result import ExecutionResultSchema

if TYPE_CHECKING:
    from src.execution.config import ExecutionTimeoutPolicy
    from src.execution.graph.factory import ExecutionGraphFactory
    from src.execution.graph.state import ExecutionGraphState
    from src.execution.state.assembler import ExecutionStateAssembler
    from src.services.action_workflow import ActionWorkflowService

logger = get_logger(__name__)


class ExecutionSession:
    """
    Runtime execution session.

    Owns request-scoped execution context while LangGraph owns
    mutable graph runtime state and checkpoint persistence.

    Action preparation is delegated to ActionWorkflowService after
    the graph produces a concrete proposed action.
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
        action_workflow_service: ActionWorkflowService,
    ) -> None:
        self._request_id = request_id
        self._conversation = conversation
        self._plan = plan
        self._context = context

        self._graph_factory = graph_factory
        self._state_assembler = state_assembler
        self._timeout_policy = timeout_policy
        self._action_workflow_service = action_workflow_service

    async def execute(
        self,
    ) -> ExecutionResultSchema:
        """
        Execute the session through the compiled LangGraph workflow.

        If the execution produces a concrete action, the action is
        passed to ActionWorkflowService for persistence, authorization,
        and approval evaluation.

        This method never waits for human approval.
        """

        logger.info(
            "Starting execution session.",
            extra={
                "operation": "execute_session",
                "request_id": str(self._request_id),
                "execution_id": self._context.execution_id,
                "thread_id": self._context.thread_id,
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
                    config={
                        "configurable": {
                            "thread_id": str(self._context.thread_id),
                        },
                    },
                ),
                timeout=self._timeout_policy.timeout_seconds,
            )

            state = self._state_assembler.assemble_state(
                graph_state=graph_state,
            )

            memory = self._state_assembler.assemble_memory(
                graph_state=graph_state,
            )

            action, approval = await self._prepare_action(
                graph_state=graph_state,
            )

            logger.info(
                "Execution session completed.",
                extra={
                    "operation": "execute_session",
                    "request_id": str(self._request_id),
                    "execution_status": state.status.value,
                    "execution_mode": self._plan.mode.value,
                    "action_present": action is not None,
                },
            )

            return ExecutionResultSchema(
                state=state,
                artifacts=dict(
                    memory.artifacts,
                ),
                action=action,
                approval=approval,
            )

        except TimeoutError as exc:
            logger.error(
                "Execution session timed out.",
                extra={
                    "operation": "execute_session_timeout",
                    "request_id": str(self._request_id),
                    "execution_mode": self._plan.mode.value,
                    "timeout_seconds": self._timeout_policy.timeout_seconds,
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

    async def _prepare_action(
        self,
        *,
        graph_state: ExecutionGraphState,
    ) -> tuple[
        AgentActionRequestDTO | None,
        ApprovalResponseDTO | None,
    ]:
        """
        Process the action proposed by the execution graph.

        Returns the persisted action and optional approval request.

        This method never waits for human approval.
        """

        action = self._state_assembler.assemble_action(
            graph_state=graph_state,
        )

        if action is None:
            return None, None

        result = await self._action_workflow_service.prepare(
            user_id=self._context.user_id,
            tenant_id=self._context.user_id,  # TODO
            action=action,
        )

        return result.action, result.approval

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
