"""
Resume a LangGraph execution after a human HITL decision.

This is the second half of the human-approval loop that
ActionWorkflowService/ApprovalLifecyclePolicy only start: something
must actually execute the approved action and continue the paused
agent turn, or the approval has no observable effect. See
agentic.execution.session.ExecutionSession._extract_interrupted_action()
and agentic.agents.runtime.continuation.AgentContinuationService.
_execute_gated_tool() for the pausing half this resumes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from agentic.tools.result import ToolResult
from application.authorization.approval_lifecycle.verifier import (
    TOOL_RESULT_KEY,
    approved_parameters,
)
from application.services.base import BaseService
from config.settings import get_settings
from core.dto.planning import deserialize_plan
from core.enums import (
    AgentActionStatusEnum,
    ApprovalDecisionEnum,
    HitlResumeStatusEnum,
    MessageRoleEnum,
)
from core.exceptions.agent_action import AgentActionError
from core.exceptions.approval import (
    ApprovalResumeNeedsConfirmationError,
    ApprovalResumeNotAllowedError,
)
from core.usage import usage_tally

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from adapters.persistence.sqlalchemy.models.agent_action import AgentAction
    from agentic.orchestration.orchestrator import AIOrchestrator
    from application.authorization.service import AuthorizationService
    from application.services.action_workflow import ActionWorkflowService
    from application.services.conversation_event import ConversationEventService
    from application.services.usage import UsageService
    from application.services.user_memory_extraction import MemoryExtractionScheduler
    from core.dto.approval import ApprovalResponseDTO

logger = get_logger(__name__)

_RESUMABLE_DECISIONS = frozenset(
    {
        ApprovalDecisionEnum.APPROVE,
        ApprovalDecisionEnum.REJECT,
        ApprovalDecisionEnum.EDIT,
    }
)

# A decided approval whose action is in one of these states hasn't
# started resuming, or failed doing so: PENDING_APPROVAL (the process
# stopped between the decision commit and the resume), FAILED (recorded
# failure). A resume claims the action by moving it to EXECUTING; an
# EXECUTING action is claimable again only by a retry, once it is stale
# (HITL_RESUME_STALE_SECONDS: the worker that claimed it stopped), and
# only with the user's confirmation if the send may already have run.
_CLAIMABLE_ACTION_STATUSES = frozenset(
    {
        AgentActionStatusEnum.PENDING_APPROVAL,
        AgentActionStatusEnum.FAILED,
    }
)


def _stale_before() -> datetime:
    """An EXECUTING action last updated before this may be claimed again."""

    seconds = get_settings().agent_policy.HITL_RESUME_STALE_SECONDS
    return datetime.now(UTC) - timedelta(seconds=seconds)


class HitlResumeService(BaseService):
    """
    Executes an approved gated tool call for real and resumes the
    paused LangGraph execution with the result, or resumes it with a
    rejection so the agent can respond gracefully instead of leaving
    the conversation stuck.

    Responsibilities:
    - reconstruct the paused execution's plan,
    - run an approved (or edited) gated call once, with the approved
      parameters, and store its result on the AgentAction before the
      graph resumes, so a retry reuses it instead of sending twice,
    - resume the graph via AIOrchestrator.resume(),
    - persist the resulting answer as a new ASSISTANT event,
    - record the outcome on the AgentAction row, including a failed
      resume (status FAILED),
    - retry a failed or interrupted resume on the owner's request
      (retry()).

    It does not:
    - evaluate approval policy,
    - process the human decision itself (ApprovalLifecycleService
      owns that; this runs AFTER the decision is committed).
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        agent_action_repository: AgentActionRepository,
        conversation_event_service: ConversationEventService,
        orchestrator: AIOrchestrator,
        action_workflow_service: ActionWorkflowService,
        authorization_service: AuthorizationService,
        usage_service: UsageService,
        memory_extraction_scheduler: MemoryExtractionScheduler | None = None,
    ) -> None:
        super().__init__(session)
        self._authorization_service = authorization_service
        self._usage_service = usage_service
        self._agent_action_repository = agent_action_repository
        self._conversation_event_service = conversation_event_service
        self._orchestrator = orchestrator
        self._action_workflow_service = action_workflow_service
        # Optional so the service works with user memory not wired
        # (api.dependencies.hitl_resume provides it).
        self._memory_extraction_scheduler = memory_extraction_scheduler

    async def resume_after_decision(
        self,
        *,
        approval_id: str,
        agent_action_id: str,
        decision_type: ApprovalDecisionEnum | None,
        edited_payload: dict[str, Any] | None = None,
        take_over_stale: bool = False,
    ) -> HitlResumeStatusEnum:
        """
        Resume the execution paused by agent_action_id's gated tool
        call, using the decision ApprovalLifecycleService has already
        committed (this runs strictly after that -- see
        api/v1/endpoints/approval.py).

        APPROVE runs the call as proposed; EDIT runs it with
        edited_payload applied over the proposal (the edit is the
        reviewer's approval of the changed draft); REJECT runs nothing.

        Never raises: the decision is already committed, so a failure
        here must not make it appear to have failed. Any failure rolls
        back only this method's own writes, is logged, is recorded on
        the AgentAction (status FAILED, result {"error": <type>,
        "approval_id": ...}) in a separate transaction, and is reported
        to the caller as FAILED. Nothing retries it automatically.

        Replay safety: the approved call's result is committed on the
        AgentAction before the graph resumes. A later failure (graph,
        event write) leaves it there, so retry() reuses the stored result
        instead of running the call again; and a thread whose graph
        already finished returns its final state unchanged on resume.

        decision_type None (a still-pending approval) is not resumed:
        returns NOT_RESUMED without touching the session.

        Concurrency: the resume first claims the action (an atomic
        conditional UPDATE to EXECUTING, committed at once), so of two
        overlapping resumes of the same action -- the decision and a
        retry, or two retries, in any workers -- only one runs the call
        and the graph. The other returns IN_PROGRESS without touching
        anything. A claim left EXECUTING by a worker that stopped is taken
        over only with take_over_stale, which retry() decides.
        """

        if decision_type not in _RESUMABLE_DECISIONS:
            return HitlResumeStatusEnum.NOT_RESUMED

        approved = decision_type in (
            ApprovalDecisionEnum.APPROVE,
            ApprovalDecisionEnum.EDIT,
        )

        try:
            claimed = await self._agent_action_repository.claim(
                agent_action_id,
                from_statuses=_CLAIMABLE_ACTION_STATUSES,
                stale_before=_stale_before() if take_over_stale else None,
            )
            await self.commit()
        except Exception:
            await self.rollback()
            logger.exception(
                "Could not claim the action for resuming.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action_id,
                },
            )
            return HitlResumeStatusEnum.FAILED

        if not claimed:
            logger.info(
                "Not resuming: the action is already being resumed or has finished.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action_id,
                },
            )
            return HitlResumeStatusEnum.IN_PROGRESS

        try:
            agent_action = await self._agent_action_repository.get(
                agent_action_id,
            )

            if agent_action is None:
                logger.error(
                    "Cannot resume: AgentAction not found for approval.",
                    extra={
                        "operation": "resume_after_decision",
                        "approval_id": approval_id,
                        "agent_action_id": agent_action_id,
                    },
                )
                return HitlResumeStatusEnum.FAILED

            if agent_action.plan_snapshot is None:
                logger.error(
                    "Cannot resume: AgentAction has no plan_snapshot -- "
                    "it wasn't created from a paused (interrupted) "
                    "execution.",
                    extra={
                        "operation": "resume_after_decision",
                        "approval_id": approval_id,
                        "agent_action_id": agent_action_id,
                    },
                )
                return HitlResumeStatusEnum.FAILED

            plan = deserialize_plan(agent_action.plan_snapshot)

            conversation_event = await self._conversation_event_service.get_by_id(
                event_id=agent_action.conversation_event_id,
            )

            if conversation_event is None:
                raise AgentActionError(
                    "Cannot resume: originating conversation event not found.",
                )

            tool_result = (
                await self._approved_tool_result(
                    agent_action=agent_action,
                    approval_id=approval_id,
                    edited_payload=edited_payload,
                )
                if approved
                else None
            )

            agent_action.status = AgentActionStatusEnum.EXECUTING
            await self.flush()

            # The resumed turn is its own request: its answer event and
            # its usage are keyed by this id (see the event below).
            resume_request_id = uuid4()
            user_id = agent_action.user_id

            with usage_tally() as tally:
                try:
                    response = await self._orchestrator.resume(
                        thread_id=agent_action.thread_id,
                        user_id=user_id,
                        conversation_id=conversation_event.conversation_id,
                        plan=plan,
                        approved=approved,
                        tool_result=tool_result,
                        action_workflow_service=self._action_workflow_service,
                    )
                finally:
                    # The resumed turn's LLM calls count toward the user's
                    # daily token quota, like any chat turn's, whether or
                    # not the resume then succeeds (review R19). Once per
                    # request id; record() uses its own session and never
                    # raises.
                    await self._usage_service.record(
                        user_id=user_id,
                        request_id=str(resume_request_id),
                        input_tokens=tally.prompt_tokens,
                        output_tokens=tally.completion_tokens,
                    )

            metadata: dict[str, Any] = {"resumed_agent_action_id": agent_action.id}

            if response.approval is not None:
                # The resumed turn proposed another gated action; its
                # approval is recorded the same way ChatService records
                # a turn's first one.
                metadata["approval"] = response.approval.model_dump(mode="json")

            await self._conversation_event_service.create(
                conversation_id=conversation_event.conversation_id,
                # A fresh UUID, NOT the original request's -- the
                # original request_id already produced an ASSISTANT
                # event (the "pending approval" placeholder created by
                # ChatService.chat() before this resume ever runs), and
                # conversation_events enforces at most one event per
                # (conversation_id, request_id, role)
                # (uq_conversation_event_request_role -- see
                # ConversationEvent's docstring). Reusing the original
                # request_id here violated that constraint on every
                # real approve/reject resume -- found building the HITL
                # approve-flow E2E test (tests/e2e/
                # test_hitl_approval_flow.py), the first thing to
                # exercise this path against the real constraint. A
                # resumed turn is logically its own event, triggered by
                # the approval decision rather than a new inbound HTTP
                # request, so it earns its own request_id rather than
                # borrowing one that's already spoken for.
                request_id=resume_request_id,
                parent_event_id=conversation_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=response.content,
                metadata=metadata,
            )

            agent_action.status = (
                AgentActionStatusEnum.COMPLETED if approved else AgentActionStatusEnum.REJECTED
            )
            agent_action.result = {
                **(agent_action.result or {}),
                "content": response.content,
            }
            agent_action.executed_at = datetime.now(UTC)

            conversation_id = conversation_event.conversation_id

            await self.commit()

        except Exception as exc:
            # The rollback expires every ORM instance loaded on this
            # session, including agent_action; reading its attributes
            # afterwards would lazy-load outside the async context
            # (MissingGreenlet). Only the method's own arguments are
            # used from here on, and the action is re-fetched.
            await self.rollback()

            logger.exception(
                "Failed to resume execution after HITL decision -- the "
                "decision is committed, but the conversation was not "
                "updated.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action_id,
                },
            )

            await self._record_failure(
                approval_id=approval_id,
                agent_action_id=agent_action_id,
                error=type(exc).__name__,
            )

            return HitlResumeStatusEnum.FAILED

        else:
            # After the commit, like ChatService: the extractor only ever
            # sees a finished turn. A resume adds no new USER message, so
            # this usually finds nothing new and does nothing; it matters
            # when the run scheduled by the paused chat turn was skipped
            # because another was already in flight for the conversation.
            # Fire-and-forget; it re-checks consent and the conversation
            # switch itself and never raises.
            if self._memory_extraction_scheduler is not None:
                self._memory_extraction_scheduler.schedule(
                    user_id=user_id,
                    conversation_id=conversation_id,
                )

            logger.info(
                "Resumed execution after HITL decision.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action_id,
                    "approved": approved,
                },
            )

            return HitlResumeStatusEnum.COMPLETED

    async def retry(
        self,
        *,
        approval: ApprovalResponseDTO,
        force: bool = False,
    ) -> HitlResumeStatusEnum:
        """
        Re-run the resume for a decided approval whose conversation is
        stuck: the resume failed (AgentAction FAILED), or the process
        stopped between committing the decision and finishing the resume
        (AgentAction still PENDING_APPROVAL, or EXECUTING with no
        progress for HITL_RESUME_STALE_SECONDS).

        A stale EXECUTING action of an approved call with no stored result
        may have sent before its worker stopped. Its retry raises
        ApprovalResumeNeedsConfirmationError (409, possibly_sent) unless
        force is set; a forced one is logged at WARNING and then sends
        once. A stored result, or a rejection, can't send again, so it
        needs no confirmation.

        The caller has already checked the approval belongs to the user
        (ApprovalLifecycleService.get(user_id=...)). Raises
        ApprovalResumeNotAllowedError (409) for an approval that is not
        decided, whose resume already finished, or that another request
        is resuming right now. Replay-safe: see resume_after_decision().
        """

        if approval.decision_type not in _RESUMABLE_DECISIONS:
            raise ApprovalResumeNotAllowedError(
                "Approval has not been decided, so there is nothing to resume.",
            )

        agent_action = await self._agent_action_repository.get(
            approval.agent_action_id,
        )

        if agent_action is None or (
            agent_action.status not in _CLAIMABLE_ACTION_STATUSES
            and agent_action.status is not AgentActionStatusEnum.EXECUTING
        ):
            raise ApprovalResumeNotAllowedError(
                "This approval's action has already been resumed.",
            )

        take_over_stale = (
            agent_action.status is AgentActionStatusEnum.EXECUTING
            and agent_action.updated_at < _stale_before()
        )

        if take_over_stale and self._may_have_sent(agent_action, approval):
            if not force:
                raise ApprovalResumeNeedsConfirmationError(
                    "The approved message may already have been sent. "
                    "Retry with force=true to send it anyway.",
                    details={"possibly_sent": True},
                )

            logger.warning(
                "Retrying a stale approved send without a recorded outcome, as "
                "confirmed by the user: the message may be sent twice.",
                extra={
                    "operation": "retry_resume",
                    "approval_id": approval.approval_id,
                    "agent_action_id": agent_action.id,
                    "user_id": agent_action.user_id,
                },
            )

        logger.info(
            "Retrying resume after HITL decision.",
            extra={
                "operation": "retry_resume",
                "approval_id": approval.approval_id,
                "agent_action_id": approval.agent_action_id,
                "action_status": agent_action.status.value,
            },
        )

        status = await self.resume_after_decision(
            approval_id=approval.approval_id,
            agent_action_id=approval.agent_action_id,
            decision_type=approval.decision_type,
            edited_payload=approval.edited_payload,
            take_over_stale=take_over_stale,
        )

        if status is HitlResumeStatusEnum.IN_PROGRESS:
            # Lost the claim: another request is resuming it, or it was
            # claimed too recently to be taken over.
            raise ApprovalResumeNotAllowedError(
                "This approval's action is already being resumed. Try again later.",
            )

        return status

    @staticmethod
    def _may_have_sent(
        agent_action: AgentAction,
        approval: ApprovalResponseDTO,
    ) -> bool:
        """
        Whether taking over this action could send a second time: an
        approved (or edited) call whose outcome was never stored.
        """

        return (
            approval.decision_type is not ApprovalDecisionEnum.REJECT
            and (agent_action.result or {}).get(TOOL_RESULT_KEY) is None
        )

    async def _approved_tool_result(
        self,
        *,
        agent_action: AgentAction,
        approval_id: str,
        edited_payload: dict[str, Any] | None,
    ) -> ToolResult:
        """
        The result of the approved gated call: the stored one when an
        earlier attempt already ran it, otherwise run it now and commit
        the result before anything else can fail.
        """

        stored = (agent_action.result or {}).get(TOOL_RESULT_KEY)

        if stored is not None:
            logger.info(
                "Reusing the stored result of an approved call; not running it again.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action.id,
                },
            )
            return ToolResult.from_dict(stored)

        # Re-check the user's CURRENT permission before a fresh call: the
        # action was authorized when it was prepared, but the user's role
        # may have changed since (roles are data). A stored result above
        # is not re-checked -- it is the output of a call that already ran.
        authorization = await self._authorization_service.authorize_action(
            user_id=agent_action.user_id,
            action=agent_action.to_dto(),
        )

        if authorization.is_allowed:
            tool_result = await self._orchestrator.run_approved_tool(
                tool_name=agent_action.tool_name or "",
                parameters=approved_parameters(
                    proposed=agent_action.parameters,
                    edited_payload=edited_payload,
                ),
                approval_token=approval_id,
            )
        else:
            logger.warning(
                "Approved action no longer authorized for the user; not running it.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action.id,
                    "reason": authorization.reason,
                },
            )
            tool_result = ToolResult(
                tool_name=agent_action.tool_name or "",
                success=False,
                content="",
                evidence=(),
                execution_metadata={"error_type": "PermissionDenied"},
                error="You are no longer permitted to perform this action, so it was not carried out.",
            )

        # Committed now, in its own transaction: from here on the call
        # has happened (or was refused), whatever fails next. Stored even
        # when the call failed -- an external send may have gone out
        # before the error, so it is never repeated automatically (at
        # most once) -- and when it was refused, so a retry doesn't
        # re-decide it.
        agent_action.status = AgentActionStatusEnum.EXECUTING
        agent_action.result = {
            TOOL_RESULT_KEY: tool_result.to_dict(),
            "approval_id": approval_id,
        }
        agent_action.executed_at = datetime.now(UTC)
        await self.commit()

        return tool_result

    async def _record_failure(
        self,
        *,
        approval_id: str,
        agent_action_id: str,
        error: str,
    ) -> None:
        """
        Mark the AgentAction FAILED in its own transaction, so a failed
        resume is visible in the database and not only in the logs.

        Best-effort: if this write fails too, it's logged and dropped;
        the decision itself is unaffected either way.
        """

        try:
            agent_action = await self._agent_action_repository.get(
                agent_action_id,
            )

            if agent_action is None:
                return

            agent_action.status = AgentActionStatusEnum.FAILED
            # Keep a stored tool result: it records that the approved
            # call already ran, which is what makes retry() safe.
            agent_action.result = {
                **(agent_action.result or {}),
                "error": error,
                "approval_id": approval_id,
            }

            await self.commit()

        except Exception:
            await self.rollback()

            logger.exception(
                "Failed to record resume failure on the AgentAction.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action_id,
                },
            )
