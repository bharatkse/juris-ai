"""
Delegated agent turns.

When an agent delegates (a DELEGATE decision), AgentContinuationService
sends a message through the CollaborationBus. The handler registered for
each agent on the bus is a DelegatedAgentRunner, not the agent itself: it
runs the target agent's turn on the same runtime path as a plan step
(AgentExecutionNode), so the target:

- is told its own tools (AgentExecution.start(), from its own policy);
- starts from seeded evidence;
- has its TOOL_CALLs policy-checked, validated and executed by
  ToolExecutionService, with recoverable errors fed back for a retry;
- has its FINAL answer checked by the answer-quality gate;
- runs within its own execution budget.

Agents never execute tools, so this can't live on the agent. The runner
returns the target's AgentContinuationResult; the delegating side turns
it into reasoning context
(AgentContinuationService._delegation_to_reasoning_context()).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.dto.agent import AgentRequestDTO

if TYPE_CHECKING:
    from agentic.agents.runtime.continuation import (
        AgentContinuationResult,
        AgentContinuationService,
    )
    from agentic.agents.runtime.execution import AgentExecution
    from core.models.message import AgentMessageSchema


class DelegatedAgentRunner:
    """
    CollaborationBus handler that runs one agent's delegated turn.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        agent_execution: AgentExecution,
        continuation_service: AgentContinuationService,
    ) -> None:
        self._agent_id = agent_id
        self._agent_execution = agent_execution
        self._continuation_service = continuation_service

    async def handle_message(
        self,
        *,
        message: AgentMessageSchema,
    ) -> AgentContinuationResult:
        """
        Run the target agent's turn to a final answer or a terminal result.

        The message carries the delegating agent's request and the
        delegation parameters, which are merged into the arguments. The
        request's tool_catalog is the delegating agent's; start()
        replaces it with this agent's own.
        """

        payload = message.payload

        request = payload.get("request")

        if not isinstance(request, AgentRequestDTO):
            raise ValueError(
                "Agent collaboration message is missing a valid AgentRequestDTO.",
            )

        parameters = payload.get("parameters", {})

        if not isinstance(parameters, dict):
            raise ValueError(
                "Agent collaboration message parameters must be a dictionary.",
            )

        handle = await self._agent_execution.start(
            agent_id=self._agent_id,
            request=replace(
                request,
                arguments={**request.arguments, **parameters},
                tool_catalog=(),
            ),
        )

        # The same sequence as AgentExecutionNode.__call__ for a plan step.
        await self._continuation_service.seed_evidence(handle=handle)

        initial_result = await handle.reason()

        return await self._continuation_service.execute(
            handle=handle,
            initial_result=initial_result,
        )
