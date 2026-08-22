"""
Execution runtime coordinator.
"""

from __future__ import annotations

from uuid import UUID

from src.core.dto.agent import AgentContextDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO
from src.execution.config import ExecutionTimeoutPolicy
from src.execution.graph.factory import ExecutionGraphFactory
from src.execution.schemas.result import ExecutionResultSchema
from src.execution.session import ExecutionSession
from src.execution.state import ExecutionStateAssembler
from src.services.action_workflow import ActionWorkflowService


class Executor:
    """
    Creates a request-scoped execution session.

    The Executor owns execution coordination only.
    Request-scoped application services are passed into
    the execution session.
    """

    def __init__(
        self,
        *,
        graph_factory: ExecutionGraphFactory,
        state_assembler: ExecutionStateAssembler,
        timeout_policy: ExecutionTimeoutPolicy,
    ) -> None:
        self._graph_factory = graph_factory
        self._state_assembler = state_assembler
        self._timeout_policy = timeout_policy

    async def execute(
        self,
        *,
        request_id: UUID,
        conversation: ConversationDTO,
        plan: ExecutionPlanDTO,
        context: AgentContextDTO,
        action_workflow_service: ActionWorkflowService,
    ) -> ExecutionResultSchema:
        """
        Execute an execution plan.

        The ActionWorkflowService is request-scoped and therefore
        supplied by the caller rather than stored on the runtime
        Executor.
        """

        session = ExecutionSession(
            request_id=request_id,
            conversation=conversation,
            plan=plan,
            context=context,
            graph_factory=self._graph_factory,
            state_assembler=self._state_assembler,
            timeout_policy=self._timeout_policy,
            action_workflow_service=action_workflow_service,
        )

        return await session.execute()
