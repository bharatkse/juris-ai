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

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from application.services.base import BaseService
from core.dto.planning import deserialize_plan
from core.enums import (
    AgentActionStatusEnum,
    ApprovalDecisionEnum,
    MessageRoleEnum,
)
from core.exceptions.agent_action import AgentActionError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from agentic.orchestration.orchestrator import AIOrchestrator
    from application.services.action_workflow import ActionWorkflowService
    from application.services.conversation_event import ConversationEventService
    from application.services.user_memory_extraction import MemoryExtractionScheduler

logger = get_logger(__name__)


class HitlResumeService(BaseService):
    """
    Executes an approved gated tool call for real and resumes the
    paused LangGraph execution with the result, or resumes it with a
    rejection so the agent can respond gracefully instead of leaving
    the conversation stuck.

    Responsibilities:
    - reconstruct the paused execution's plan,
    - resume it via AIOrchestrator.resume(),
    - persist the resulting answer as a new ASSISTANT event,
    - record the outcome on the AgentAction row.

    It does not:
    - evaluate approval policy,
    - process the human decision itself (ApprovalLifecycleService
      owns that; this runs AFTER a decision is already recorded).
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        agent_action_repository: AgentActionRepository,
        conversation_event_service: ConversationEventService,
        orchestrator: AIOrchestrator,
        action_workflow_service: ActionWorkflowService,
        memory_extraction_scheduler: MemoryExtractionScheduler | None = None,
    ) -> None:
        super().__init__(session)
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
    ) -> None:
        """
        Resume the execution paused by agent_action_id's gated tool
        call, using the decision already recorded by
        ApprovalLifecycleService (this runs strictly after that, using
        its result -- see api/v1/endpoints/approval.py).

        Best-effort by design, same posture as UsageService.record():
        the human's approve/reject decision has already been durably
        recorded by ApprovalLifecycleService by the time this runs, so
        a failure here must not make that decision appear to have
        failed. It's logged, not swallowed silently, and surfaces as a
        stuck (still-waiting) execution rather than a lost decision --
        recoverable by retrying resume, unlike losing the decision
        itself would be.

        decision_type other than APPROVE/REJECT (e.g. an EDIT, or None
        for a still-pending approval) is not resumable -- EDIT changes
        the proposed payload and needs its own review pass before
        anything executes, which isn't implemented; the approval stays
        WAITING until a real APPROVE/REJECT is recorded on it.
        """

        if decision_type not in (
            ApprovalDecisionEnum.APPROVE,
            ApprovalDecisionEnum.REJECT,
        ):
            return

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
            return

        if agent_action.plan_snapshot is None:
            logger.error(
                "Cannot resume: AgentAction has no plan_snapshot -- "
                "it wasn't created from a paused (interrupted) "
                "execution.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action.id,
                },
            )
            return

        approved = decision_type == ApprovalDecisionEnum.APPROVE

        try:
            plan = deserialize_plan(agent_action.plan_snapshot)

            conversation_event = await self._conversation_event_service.get_by_id(
                event_id=agent_action.conversation_event_id,
            )

            if conversation_event is None:
                raise AgentActionError(
                    "Cannot resume: originating conversation event not found.",
                )

            agent_action.status = AgentActionStatusEnum.EXECUTING
            await self.flush()

            response = await self._orchestrator.resume(
                thread_id=agent_action.thread_id,
                user_id=agent_action.user_id,
                conversation_id=conversation_event.conversation_id,
                plan=plan,
                approved=approved,
                tool_name=agent_action.tool_name or "",
                parameters=dict(agent_action.parameters),
                action_workflow_service=self._action_workflow_service,
            )

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
                request_id=uuid4(),
                parent_event_id=conversation_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=response.content,
                metadata={"resumed_agent_action_id": agent_action.id},
            )

            agent_action.status = (
                AgentActionStatusEnum.COMPLETED if approved else AgentActionStatusEnum.REJECTED
            )
            agent_action.result = {"content": response.content}
            agent_action.executed_at = datetime.now(UTC)

            await self.commit()

            # After the commit, like ChatService: the extractor only ever
            # sees a finished turn. A resume adds no new USER message, so
            # this usually finds nothing new and does nothing; it matters
            # when the run scheduled by the paused chat turn was skipped
            # because another was already in flight for the conversation.
            # Fire-and-forget; it re-checks consent and the conversation
            # switch itself and never raises.
            if self._memory_extraction_scheduler is not None:
                self._memory_extraction_scheduler.schedule(
                    user_id=agent_action.user_id,
                    conversation_id=conversation_event.conversation_id,
                )

            logger.info(
                "Resumed execution after HITL decision.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action.id,
                    "approved": approved,
                },
            )

        except Exception:
            await self.rollback()

            logger.exception(
                "Failed to resume execution after HITL decision -- the "
                "human decision is still durably recorded, but the "
                "conversation was not updated. Safe to retry.",
                extra={
                    "operation": "resume_after_decision",
                    "approval_id": approval_id,
                    "agent_action_id": agent_action.id,
                },
            )
