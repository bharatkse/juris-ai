"""
Execution runtime coordinator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from agentic.execution.attachments import attachment_context
from agentic.execution.config import ExecutionTimeoutPolicy
from agentic.execution.graph.factory import ExecutionGraphFactory
from agentic.execution.schemas.result import ExecutionResultSchema
from agentic.execution.session import ExecutionSession
from agentic.execution.state import ExecutionStateAssembler
from core.dto.agent import AgentContextDTO
from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO

if TYPE_CHECKING:
    from agentic.tools.library.parser import ParserTool
    from agentic.tools.result import ToolResult
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
    application/domain services. The one exception is
    run_approved_tool(): once a human HAS approved a gated action,
    actually invoking the tool is still execution, not approval -- and it
    must happen exactly once, outside the replayed graph node (see
    AgentContinuationService._execute_gated_tool()'s docstring), so it
    belongs here.
    """

    def __init__(
        self,
        *,
        graph_factory: ExecutionGraphFactory,
        state_assembler: ExecutionStateAssembler,
        timeout_policy: ExecutionTimeoutPolicy,
        tool_execution_service: ToolExecutionService,
        attachment_parser: ParserTool,
    ) -> None:
        self._graph_factory = graph_factory
        self._state_assembler = state_assembler
        self._timeout_policy = timeout_policy
        self._tool_execution_service = tool_execution_service
        self._attachment_parser = attachment_parser

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

        Files attached to the message are parsed here, once, into the
        graph's initial reasoning_context (see execution/attachments.py),
        so every step's agent starts from them and a later resume() finds
        them in the checkpoint.
        """

        session = ExecutionSession(
            request_id=request_id,
            conversation=conversation,
            plan=plan,
            context=context,
            reasoning_context=await attachment_context(
                parser=self._attachment_parser,
                files=context.uploaded_files,
            ),
            graph_factory=self._graph_factory,
            state_assembler=self._state_assembler,
            timeout_policy=self._timeout_policy,
            action_workflow_service=action_workflow_service,
        )

        return await session.execute()

    async def run_approved_tool(
        self,
        *,
        tool_name: str,
        parameters: dict[str, object],
        approval_token: str,
    ) -> ToolResult:
        """
        Run a gated tool call a human has approved, with the approved
        (possibly edited) parameters and the approval id as its token.

        Called by HitlResumeService BEFORE resume(), which stores the
        result on the AgentAction first: that stored result is what makes
        a retried resume replay-safe (a retry reuses it and never sends
        twice). The tool itself refuses to run unless the token covers
        exactly these parameters (tools/messaging/base.py).
        """

        return await self._tool_execution_service.execute(
            tool_name=tool_name,
            parameters=dict(parameters),
            approval_token=approval_token,
        )

    async def resume(
        self,
        *,
        thread_id: str,
        user_id: str,
        plan: ExecutionPlanDTO,
        action_workflow_service: ActionWorkflowService,
        approved: bool,
        tool_result: ToolResult | None,
    ) -> ExecutionResultSchema:
        """
        Resume a LangGraph execution paused on a gated (email_send/
        slack_post) TOOL_CALL, after a human has decided it.

        An approved call has already run (run_approved_tool()) -- not
        inside the resumed node, which LangGraph replays from its own top
        (see AgentContinuationService._execute_gated_tool()'s docstring
        for why that would be unsafe). Its result is handed to the graph
        as the interrupt's resume value; the paused node picks it up and
        continues reasoning with it as ordinary tool evidence.

        Resuming a thread that already moved past the interrupt (a retry
        after the graph finished but the caller failed to persist the
        answer) re-runs nothing: LangGraph returns the thread's final
        state as it is.

        conversation/context aren't reconstructed here: LangGraph's
        checkpointer already holds everything the graph itself needs
        for thread_id. Only a session-shaped object to drive
        graph.ainvoke(Command(resume=...)) is needed, so placeholder
        values are used for the fields ExecutionSession.resume()
        doesn't read (see its docstring).
        """

        resume_value: dict[str, object]

        if approved and tool_result is not None:
            resume_value = {
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
