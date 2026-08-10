"""
Execution runtime coordinator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.core.models.conversation import Conversation
from src.core.models.planning import ExecutionPlan
from src.execution.hybrid import HybridExecutionStrategy
from src.execution.parallel import ParallelExecutionStrategy
from src.execution.sequential import SequentialExecutionStrategy
from src.execution.session import ExecutionSession
from src.registry.agent import AgentRegistry

if TYPE_CHECKING:
    from src.execution.result import ExecutionResult


class Executor:
    """
    Creates a request-scoped execution session.
    """

    def __init__(
        self,
        *,
        agent_registry: AgentRegistry,
        sequential_strategy: SequentialExecutionStrategy,
        parallel_strategy: ParallelExecutionStrategy,
        hybrid_strategy: HybridExecutionStrategy,
    ) -> None:
        self._agent_registry = agent_registry
        self._sequential_strategy = sequential_strategy
        self._parallel_strategy = parallel_strategy
        self._hybrid_strategy = hybrid_strategy

    async def execute(
        self,
        *,
        request_id: UUID,
        conversation: Conversation,
        plan: ExecutionPlan,
    ) -> ExecutionResult:
        """
        Execute an execution plan.
        """

        session = ExecutionSession(
            request_id=request_id,
            conversation=conversation,
            plan=plan,
            agent_registry=self._agent_registry,
            sequential_strategy=self._sequential_strategy,
            parallel_strategy=self._parallel_strategy,
            hybrid_strategy=self._hybrid_strategy,
        )

        return await session.execute()
