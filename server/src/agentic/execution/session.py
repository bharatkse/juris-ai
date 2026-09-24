"""
Execution runtime session.

Owns request-scoped execution context while LangGraph owns
mutable graph runtime state and checkpoint persistence.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import UUID

from langgraph.types import Command, Interrupt

from adapters.observability.logger import get_logger
from agentic.decisions.decision import AgentDecisionType
from agentic.execution.graph.state import ExecutionGraphState
from agentic.execution.schemas.result import ExecutionResultSchema
from core.dto.action_workflow import ActionWorkflowResultDTO
from core.dto.agent import AgentContextDTO, AgentStreamChunkDTO
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO, serialize_plan
from core.enums import ActionTypeEnum, ActorTypeEnum, ExecutionStatusEnum
from core.exceptions.execution import ExecutionError

if TYPE_CHECKING:
    from agentic.execution.config import ExecutionTimeoutPolicy
    from agentic.execution.graph.factory import ExecutionGraphFactory
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

            return await self._finish(
                graph_state=cast(ExecutionGraphState, graph_state),
                user_id=self._context.user_id,
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

    async def execute_streaming(
        self,
    ) -> AsyncIterator[AgentStreamChunkDTO | ExecutionResultSchema]:
        """
        Execute the request through the compiled LangGraph workflow,
        streaming the FINAL step's answer text as it is produced.

        Additive alongside execute()/resume() above -- both remain
        entirely ainvoke()-based and are untouched by this method's
        existence. The only difference in what this builds: the
        initial state's "streaming" key is set True, which is what
        AgentExecutionNode (graph/nodes.py) checks to decide whether
        to also emit the FINAL step's answer via LangGraph's custom
        stream channel. Every other step type in the same plan
        (TOOL_CALL, DELEGATE, ...) executes exactly as it does under
        execute(), streaming session or not -- see
        AgentExecutionNode._stream_final_answer_if_reached().

        Yields AgentStreamChunkDTO instances as they arrive, then
        exactly one ExecutionResultSchema as the final item -- built
        via the same _finish() execute()/resume() already use above,
        from the graph's actual final state (requested via LangGraph's
        "values" stream mode alongside "custom", not a second,
        parallel reconstruction of what execute() already does).
        Mirrors the established AgentStreamChunkDTO/ChatStreamChunkDTO
        pattern already used elsewhere in this feature (a stream of
        chunks, the last item carrying the full result) rather than
        inventing a new shape.
        """

        logger.info(
            "Starting streaming execution session.",
            extra={
                "operation": "execute_streaming_session",
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
            initial_state["streaming"] = True

            final_graph_state: ExecutionGraphState | None = None

            async with asyncio.timeout(
                self._timeout_policy.timeout_seconds,
            ):
                # Two stream modes at once, not two separate calls:
                # LangGraph interleaves both kinds of event, in
                # execution order, as (mode, payload) tuples -- "values"
                # yields the graph state after every node completes
                # (its own first event, before any node has even run,
                # is the initial state; its last is exactly what
                # ainvoke() would have returned). Verified empirically
                # against this project's own graph/checkpointer setup
                # before writing this, not assumed from documentation
                # alone.
                async for mode, event in graph.astream(
                    initial_state,
                    config={
                        "configurable": {
                            "thread_id": self._context.thread_id,
                        },
                    },
                    stream_mode=["custom", "values"],
                ):
                    if mode == "custom":
                        # graph.astream()'s declared return type is the
                        # generic AsyncIterator[dict[str, Any] | Any] --
                        # LangGraph's custom stream mode has no way to
                        # type the payload a node's writer actually
                        # sends. The real, guaranteed type is
                        # AgentStreamChunkDTO:
                        # AgentExecutionNode._stream_final_answer_if_reached()
                        # is this graph's only writer() caller, and it
                        # only ever writes that type.
                        yield cast(AgentStreamChunkDTO, event)
                    else:
                        final_graph_state = cast(ExecutionGraphState, event)

            if final_graph_state is None:
                # Defensive, not expected to be reachable: "values"
                # mode's own first event is always the initial state,
                # emitted before any node runs -- see the comment
                # above. Same shape as stream_chat()'s equivalent
                # guard (application/services/chat.py) for a stream
                # that ends without ever producing what it promises.
                raise ExecutionError(
                    message="Streaming execution completed without a final graph state.",
                )

            yield await self._finish(
                graph_state=final_graph_state,
                user_id=self._context.user_id,
            )

        except TimeoutError as exc:
            logger.error(
                "Streaming execution session timed out.",
                extra={
                    "operation": "execute_streaming_session_timeout",
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
                "Streaming execution session failed.",
                extra={
                    "operation": "execute_streaming_session",
                    "request_id": str(self._request_id),
                    "execution_id": self._context.execution_id,
                    "execution_mode": self._plan.mode.value,
                },
            )

            raise

    async def resume(
        self,
        *,
        thread_id: str,
        user_id: str,
        resume_value: dict[str, object],
    ) -> ExecutionResultSchema:
        """
        Resume a previously-interrupted execution on the same thread.

        Callers (Executor.resume()) are responsible for computing
        resume_value BEFORE calling this -- if a gated tool call was
        approved, the tool must already have been executed for real,
        with its result embedded in resume_value, since the node that
        called interrupt() replays from its own top on resume and must
        not re-trigger the side effect itself. See
        AgentContinuationService._execute_gated_tool()'s docstring.

        No initial_state is built here: LangGraph reloads the
        checkpointed state for thread_id automatically. This session
        instance only needs the same plan (to rebuild an identically
        shaped compiled graph) and the resume payload.
        """

        logger.info(
            "Resuming execution session.",
            extra={
                "operation": "resume_session",
                "request_id": str(self._request_id),
                "thread_id": thread_id,
                "execution_mode": self._plan.mode.value,
            },
        )

        try:
            graph = self._graph_factory.create(
                plan=self._plan,
            )

            graph_state = await asyncio.wait_for(
                graph.ainvoke(
                    Command(resume=resume_value),
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                        },
                    },
                ),
                timeout=self._timeout_policy.timeout_seconds,
            )

            return await self._finish(
                graph_state=cast(ExecutionGraphState, graph_state),
                user_id=user_id,
            )

        except TimeoutError as exc:
            logger.error(
                "Execution session resume timed out.",
                extra={
                    "operation": "resume_session_timeout",
                    "request_id": str(self._request_id),
                    "thread_id": thread_id,
                    "timeout_seconds": self._timeout_policy.timeout_seconds,
                },
            )

            raise ExecutionError(
                message=(
                    "Execution resume timed out after "
                    f"{self._timeout_policy.timeout_seconds} seconds."
                ),
            ) from exc

        except Exception:
            logger.exception(
                "Execution session resume failed.",
                extra={
                    "operation": "resume_session",
                    "request_id": str(self._request_id),
                    "thread_id": thread_id,
                },
            )

            raise

    async def _finish(
        self,
        *,
        graph_state: ExecutionGraphState,
        user_id: str,
    ) -> ExecutionResultSchema:
        """
        Shared tail for both a fresh execution and a resumed one:
        forward any pending business action, assemble state/memory,
        and build the ExecutionResultSchema.
        """

        workflow_result = await self._prepare_action(
            graph_state=graph_state,
            user_id=user_id,
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

    async def _prepare_action(
        self,
        *,
        graph_state: ExecutionGraphState,
        user_id: str,
    ) -> ActionWorkflowResultDTO | None:
        """
        Forward a concrete business action to ActionWorkflowService.

        Two independent sources of a "concrete business action" exist:

        1. A LangGraph interrupt (graph_state["__interrupt__"]) --
           AgentContinuationService paused mid-turn on a GATED_TOOLS
           TOOL_CALL (see continuation.py's _execute_gated_tool()).
           This is real: the graph is genuinely suspended and the
           checkpointer holds everything needed to resume it later.

        2. graph_state["action"] via the state assembler -- the
           pre-existing path for a decision that completes a node
           without pausing. Internal TOOL_CALL/DELEGATE decisions are
           filtered out here (they're consumed inside
           AgentContinuationService and must never cross the
           business-action boundary); nothing else populates this
           today, so this path is currently unreachable in practice,
           kept only so a future non-interrupt-based business action
           has somewhere to plug in without another wiring change.

        ActionWorkflowService owns:
            - persistence
            - authorization
            - approval-policy evaluation
            - approval-request creation

        This method never waits for human approval.
        """

        interrupted_action = self._extract_interrupted_action(
            graph_state=graph_state,
        )

        if interrupted_action is not None:
            return await self._action_workflow_service.prepare(
                user_id=user_id,
                tenant_id=user_id,
                action=interrupted_action,
                plan_snapshot=serialize_plan(self._plan),
            )

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
            user_id=user_id,
            tenant_id=user_id,
            action=action,
        )

    @staticmethod
    def _extract_interrupted_action(
        *,
        graph_state: ExecutionGraphState,
    ) -> AgentActionRequestDTO | None:
        """
        Rebuild the AgentActionRequestDTO from a LangGraph interrupt
        payload, if the graph is currently paused.

        The payload is a plain dict (see _execute_gated_tool()), not
        the dataclass itself -- interrupt()/the checkpointer only
        reliably round-trip JSON-primitive types.
        """

        # LangGraph adds "__interrupt__" to the returned state; it is
        # not part of the declared ExecutionGraphState schema.
        interrupts = cast("list[Interrupt] | None", graph_state.get("__interrupt__"))

        if not interrupts:
            return None

        # Exactly one gated tool call pauses one node at a time in
        # today's single-node-per-step graph shape.
        payload = interrupts[0].value

        return AgentActionRequestDTO(
            execution_id=payload["execution_id"],
            thread_id=payload["thread_id"],
            conversation_event_id=payload["conversation_event_id"],
            agent_id=payload["agent_id"],
            action_type=ActionTypeEnum(payload["action_type"]),
            actor_type=ActorTypeEnum(payload["actor_type"]),
            tool_name=payload["tool_name"],
            parameters=payload["parameters"],
            reason=payload["reason"],
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
            "termination_reason": None,
        }
