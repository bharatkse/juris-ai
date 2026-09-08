"""
Execution runtime session.

Owns request-scoped execution context while LangGraph owns
mutable graph runtime state and checkpoint persistence.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from adapters.observability.logger import get_logger
from agentic.decisions.decision import AgentDecisionType
from agentic.execution.schemas.result import ExecutionResultSchema
from core.dto.action_workflow import ActionWorkflowResultDTO
from core.dto.agent import AgentContextDTO
from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO
from core.enums import ExecutionStatusEnum
from core.exceptions.execution import ExecutionError

if TYPE_CHECKING:
    from agentic.execution.config import ExecutionTimeoutPolicy
    from agentic.execution.graph.factory import ExecutionGraphFactory
    from agentic.execution.graph.state import ExecutionGraphState
    from agentic.execution.state.assembler import ExecutionStateAssembler
    from application.services.action_workflow import ActionWorkflowService


logger = get_logger(__name__)


class ExecutionSession:
    """
    Request-scoped execution session.

    Responsibilities:
        - own immutable request/session context
        - create initial graph state
        - invoke the execution graph
        - assemble execution state and memory
        - forward concrete business actions to ActionWorkflowService

    This class does not:
        - perform agent reasoning
        - execute tools
        - invoke agents directly
        - perform planning
        - wait for human approval
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

    async def execute(self) -> ExecutionResultSchema:
        """
        Execute the request through the compiled LangGraph workflow.

        The session is request-scoped. No mutable execution state is
        stored outside the LangGraph/checkpoint runtime.
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
                            "thread_id": self._context.thread_id,
                        },
                    },
                ),
                timeout=self._timeout_policy.timeout_seconds,
            )

            workflow_result = await self._prepare_action(
                graph_state=graph_state,
            )

            state = self._state_assembler.assemble_state(
                graph_state=graph_state,
            )

            if workflow_result is not None and workflow_result.approval_required:
                state.status = ExecutionStatusEnum.WAITING_FOR_APPROVAL

            memory = self._state_assembler.assemble_memory(
                graph_state=graph_state,
            )

            action = workflow_result.action if workflow_result is not None else None

            approval = workflow_result.approval if workflow_result is not None else None

            logger.info(
                "Execution session completed.",
                extra={
                    "operation": "execute_session",
                    "request_id": str(self._request_id),
                    "execution_id": self._context.execution_id,
                    "execution_status": state.status.value,
                    "execution_mode": self._plan.mode.value,
                    "action_present": action is not None,
                    "approval_required": (
                        workflow_result.approval_required if workflow_result is not None else False
                    ),
                },
            )

            return ExecutionResultSchema(
                state=state,
                artifacts=dict(memory.artifacts),
                action=action,
                approval=approval,
            )

        except TimeoutError as exc:
            logger.error(
                "Execution session timed out.",
                extra={
                    "operation": "execute_session_timeout",
                    "request_id": str(self._request_id),
                    "execution_id": self._context.execution_id,
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
                    "execution_id": self._context.execution_id,
                    "execution_mode": self._plan.mode.value,
                },
            )

            raise

    async def _prepare_action(
        self,
        *,
        graph_state: ExecutionGraphState,
    ) -> ActionWorkflowResultDTO | None:
        """
        Forward a concrete business action to ActionWorkflowService.

        Internal TOOL_CALL and DELEGATE decisions are consumed by
        AgentContinuationService and must never cross the business-action
        boundary.

        ActionWorkflowService owns:
            - persistence
            - authorization
            - approval-policy evaluation
            - approval-request creation

        This method never waits for human approval.
        """

        action = self._state_assembler.assemble_action(
            graph_state=graph_state,
        )

        if action is None:
            return None

        if self._is_internal_agent_action(
            graph_state=graph_state,
        ):
            logger.debug(
                "Ignoring internal agent action at business-action boundary.",
                extra={
                    "operation": "prepare_action",
                    "request_id": str(self._request_id),
                    "execution_id": self._context.execution_id,
                    "action_type": action.action_type.value,
                    "tool_name": action.tool_name,
                    "target_agent_id": action.target_agent_id,
                },
            )
            return None

        return await self._action_workflow_service.prepare(
            user_id=self._context.user_id,
            tenant_id=self._context.user_id,
            action=action,
        )

    @staticmethod
    def _is_internal_agent_action(
        *,
        graph_state: ExecutionGraphState,
    ) -> bool:
        """
        Return whether the graph's latest agent decision represents
        an internal continuation operation.

        TOOL_CALL and DELEGATE are consumed inside the agent execution
        continuation boundary and must not be processed as concrete
        business actions.
        """

        decision_updates = graph_state["agent_decision_updates"]

        if not decision_updates:
            return False

        latest_decision = decision_updates[-1]["decision"]

        return latest_decision.decision_type in {
            AgentDecisionType.TOOL_CALL,
            AgentDecisionType.DELEGATE,
        }

    def _build_initial_state(self) -> ExecutionGraphState:
        """
        Build the initial LangGraph state for this request.

        All values are request-scoped.

        No mutable state is retained by ExecutionSession after
        graph execution completes.
        """

        started_at = datetime.now(UTC)

        deadline = started_at + timedelta(
            seconds=self._timeout_policy.timeout_seconds,
        )

        return {
            "request_id": self._request_id,
            "started_at": started_at,
            "deadline": deadline,
            "conversation": self._conversation,
            "context": self._context,
            "reasoning_context": [],
            "plan": self._plan,
            "execution_state_updates": [],
            "memory_updates": [],
            "agent_decision_updates": [],
            "action": None,
        }
