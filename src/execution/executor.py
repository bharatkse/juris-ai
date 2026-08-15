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


class Executor:
    """
    Creates a request-scoped execution session.
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
    ) -> ExecutionResultSchema:
        """
        Execute an execution plan.
        """

        session = ExecutionSession(
            request_id=request_id,
            conversation=conversation,
            plan=plan,
            context=context,
            graph_factory=self._graph_factory,
            state_assembler=self._state_assembler,
            timeout_policy=self._timeout_policy,
        )

        return await session.execute()
