"""
Execution runtime coordinator.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from agentic.execution.config import ExecutionTimeoutPolicy
from agentic.execution.graph.factory import ExecutionGraphFactory
from agentic.execution.schemas.result import ExecutionResultSchema
from agentic.execution.session import ExecutionSession
from agentic.execution.state import ExecutionStateAssembler
from core.dto.agent import AgentContextDTO, AgentStreamChunkDTO
from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO

if TYPE_CHECKING:
    from agentic.tools.runtime.invocation import ToolExecutionService
    from application.services.action_workflow import ActionWorkflowService


class Executor:
    """
    Coordinates execution of a validated ExecutionPlan.

    The Executor owns execution coordination only.

    It does not:
    - create execution plans,
    - perform authorization,
    - evaluate approval policy,
    - create approval requests,
    - wait for human approval.

    Those responsibilities belong to their respective
    application/domain services. The one exception is resume(): once a
    human HAS approved a gated action, actually invoking the tool is
    still execution, not approval -- and it must happen exactly once,
    outside the replayed graph node (see AgentContinuationService.
    _execute_gated_tool()'s docstring), so it belongs here.
    """

    def __init__(
        self,
        *,
        graph_factory: ExecutionGraphFactory,
        state_assembler: ExecutionStateAssembler,
        timeout_policy: ExecutionTimeoutPolicy,
        tool_execution_service: ToolExecutionService,
    ) -> None:
        self._graph_factory = graph_factory
        self._state_assembler = state_assembler
        self._timeout_policy = timeout_policy
        self._tool_execution_service = tool_execution_service

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

    async def execute_streaming(
        self,
        *,
        request_id: UUID,
        conversation: ConversationDTO,
        plan: ExecutionPlanDTO,
        context: AgentContextDTO,
        action_workflow_service: ActionWorkflowService,
    ) -> AsyncIterator[AgentStreamChunkDTO | ExecutionResultSchema]:
        """
        Streaming counterpart to execute() above -- same
        ExecutionSession construction, calling session.execute_streaming()
        instead of session.execute(). See that method's docstring for
        the yielded shape (AgentStreamChunkDTO instances, then exactly
        one ExecutionResultSchema as the final item).
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

        async for item in session.execute_streaming():
            yield item

    async def resume(
        self,
        *,
        thread_id: str,
        user_id: str,
        plan: ExecutionPlanDTO,
        action_workflow_service: ActionWorkflowService,
        approved: bool,
        tool_name: str,
        parameters: dict[str, object],
    ) -> ExecutionResultSchema:
        """
        Resume a LangGraph execution paused on a gated (email/slack
        send) TOOL_CALL, after a human has approved or rejected it.

        If approved, the tool is executed for REAL here, before the
        graph resumes -- not inside the resumed node, which LangGraph
        replays from its own top (see AgentContinuationService.
        _execute_gated_tool()'s docstring for why that would be unsafe
        to do inside the graph). The real result is handed to the
        graph as the interrupt's resume value; the paused node's code
        picks it up and continues reasoning with it as ordinary tool
        evidence.

        conversation/context aren't reconstructed here: LangGraph's
        checkpointer already holds everything the graph itself needs
        for thread_id. Only a session-shaped object to drive
        graph.ainvoke(Command(resume=...)) is needed, so placeholder
        values are used for the fields ExecutionSession.resume()
        doesn't read (see its docstring).
        """

        if approved:
            tool_result = await self._tool_execution_service.execute(
                tool_name=tool_name,
                parameters=parameters,
            )

            resume_value: dict[str, object] = {
                "decision": "approved",
                "tool_result": tool_result.to_dict(),
            }
        else:
            resume_value = {"decision": "rejected"}

        session = ExecutionSession(
            request_id=uuid4(),
            conversation=ConversationDTO(messages=()),
            plan=plan,
            context=AgentContextDTO(
                user_id=user_id,
                execution_id="resume",
                thread_id=thread_id,
                conversation_event_id="resume",
            ),
            graph_factory=self._graph_factory,
            state_assembler=self._state_assembler,
            timeout_policy=self._timeout_policy,
            action_workflow_service=action_workflow_service,
        )

        return await session.resume(
            thread_id=thread_id,
            user_id=user_id,
            resume_value=resume_value,
        )
