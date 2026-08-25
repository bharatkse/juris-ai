"""
Execution runtime coordinator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.core.dto.agent import AgentContextDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO
from src.execution.config import ExecutionTimeoutPolicy
from src.execution.graph.factory import ExecutionGraphFactory
from src.execution.schemas.result import ExecutionResultSchema
from src.execution.session import ExecutionSession
from src.execution.state import ExecutionStateAssembler

if TYPE_CHECKING:
    from src.services.action_workflow import ActionWorkflowService


class Executor:
    """
    Coordinates execution of a validated ExecutionPlan.

    The Executor owns execution coordination only.

    It does not:
    - create execution plans,
    - perform authorization,
    - evaluate approval policy,
    - create approval requests,
    - wait for human approval,
    - execute approved actions.

    Those responsibilities belong to their respective
    application/domain services.
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
        Execute a validated execution plan.

        A request-scoped ExecutionSession is created for the
        execution. LangGraph owns the runtime graph state and
        checkpoint persistence.
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
