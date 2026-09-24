"""
Compliance/legal-discovery audit trail.

Deliberately separate from OpenTelemetry tracing (adapters/observability/
telemetry.py, tracing.py): OTel is debugging/performance instrumentation
-- off by default (OTEL_TRACING), exported via a BatchSpanProcessor that
is explicitly fire-and-forget, and meant to be sampled/rolled off. A
compliance record must never be silently disabled by a tracing flag,
so it is not built on that infrastructure. Also deliberately separate
from conversation_events: that table serves the chat UI and is subject
to a user's own conversation deletion; a firm's compliance obligations
must not evaporate when a user deletes their chat history, so this
table's retention (config.compliance.ComplianceSettings.
COMPLIANCE_LOG_RETENTION_DAYS, None by default -- retain indefinitely)
is never coupled to that. See purge_older_than() below for the
explicit, opt-in purge mechanism this setting enables -- it does
nothing on its own; nothing in this codebase calls it automatically.

No-raw-content rule: every record_*() method here builds its own
payload shape and is the ONLY place a ComplianceLog row is ever
constructed -- callers never hand this service a raw payload dict.
Message/response text is hashed (sha256) plus length, never stored
verbatim (it already lives durably in conversation_events -- this
table needs enough to correlate/prove, not a second copy). Retrieved
evidence is stored as identifiers (source, source_name, resource_id),
never chunk content. A guardrail firing stores category/action/count,
never the matched PII substring.

Two ways to write a row, one code path underneath:
    ComplianceLogService        -- for callers that already own a
                                    request-scoped AsyncSession
                                    (ChatService, ApprovalLifecycleService)
                                    -- flushes only; the caller's own
                                    commit() covers it, same transaction
                                    as whatever else that request writes.
    StandaloneComplianceLogWriter -- for callers with no request session
                                    at all: AIOrchestrator and
                                    AgentContinuationService are both
                                    composed once at process startup
                                    (wiring/composition.py,
                                    wiring/factories/executor.py), shared
                                    across every request, never
                                    constructed per-request. Opens its
                                    own short-lived session per write and
                                    commits it immediately -- the same
                                    session_factory pattern
                                    DatabaseAgentPolicyProvider already
                                    uses (agentic/policy/agent_policy.py)
                                    for exactly this reason.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from application.services.base import BaseService
from core.enums import ActorTypeEnum, ComplianceEventTypeEnum, UserMemoryOperationEnum

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from adapters.persistence.sqlalchemy.repositories.compliance_log import (
        ComplianceLogRepository,
    )
    from core.dto.tool import RetrievedContentDTO

logger = get_logger(__name__)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ComplianceLogService(BaseService):
    """
    Writes compliance log rows for a caller that already owns a
    request-scoped AsyncSession.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: ComplianceLogRepository,
    ) -> None:
        super().__init__(session)
        self._repository = repository

    async def record_request_received(
        self,
        *,
        request_id: UUID,
        user_id: str,
        tenant_id: str,
        conversation_id: str | None,
        conversation_event_id: str | None,
        message: str,
    ) -> ComplianceLog:
        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=ActorTypeEnum.USER,
            event_type=ComplianceEventTypeEnum.REQUEST_RECEIVED,
            conversation_id=conversation_id,
            conversation_event_id=conversation_event_id,
            payload={
                "message_hash": _hash(message),
                "message_length": len(message),
            },
        )

    async def record_response_returned(
        self,
        *,
        request_id: UUID,
        user_id: str,
        tenant_id: str,
        conversation_id: str | None,
        conversation_event_id: str | None,
        content: str,
        citation_count: int,
        action_required: bool,
    ) -> ComplianceLog:
        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=ActorTypeEnum.AGENT,
            event_type=ComplianceEventTypeEnum.RESPONSE_RETURNED,
            conversation_id=conversation_id,
            conversation_event_id=conversation_event_id,
            payload={
                "content_hash": _hash(content),
                "content_length": len(content),
                "citation_count": citation_count,
                "action_required": action_required,
            },
        )

    async def record_plan_created(
        self,
        *,
        request_id: UUID,
        user_id: str,
        tenant_id: str,
        conversation_id: str | None,
        intent: str,
        mode: str,
        step_count: int,
    ) -> ComplianceLog:
        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=ActorTypeEnum.AGENT,
            event_type=ComplianceEventTypeEnum.PLAN_CREATED,
            conversation_id=conversation_id,
            payload={
                "intent": intent,
                "mode": mode,
                "step_count": step_count,
            },
        )

    async def record_retrieval_performed(
        self,
        *,
        request_id: UUID,
        user_id: str,
        tenant_id: str,
        thread_id: str | None,
        agent_id: str | None,
        retrieved: Sequence[RetrievedContentDTO],
    ) -> ComplianceLog:
        """
        Records WHAT was retrieved (source identifiers only) -- never
        RetrievedContentDTO.content, which is the actual chunk text.
        """

        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=ActorTypeEnum.AGENT,
            event_type=ComplianceEventTypeEnum.RETRIEVAL_PERFORMED,
            thread_id=thread_id,
            agent_id=agent_id,
            payload={
                "results": [
                    {
                        "source": (
                            item.source.value if hasattr(item.source, "value") else str(item.source)
                        ),
                        "source_name": item.source_name,
                        "score": item.score,
                    }
                    for item in retrieved
                ],
                "result_count": len(retrieved),
            },
        )

    async def record_tool_call_executed(
        self,
        *,
        request_id: UUID,
        user_id: str,
        tenant_id: str,
        thread_id: str | None,
        agent_id: str | None,
        tool_name: str,
        success: bool,
    ) -> ComplianceLog:
        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=ActorTypeEnum.AGENT,
            event_type=ComplianceEventTypeEnum.TOOL_CALL_EXECUTED,
            thread_id=thread_id,
            agent_id=agent_id,
            resource_type="tool",
            resource_id=tool_name,
            payload={
                "tool_name": tool_name,
                "success": success,
            },
        )

    async def record_agent_decision(
        self,
        *,
        request_id: UUID,
        user_id: str,
        tenant_id: str,
        conversation_id: str | None,
        agent_id: str | None,
        decision_type: str,
        groundedness: float | None = None,
        relevance: float | None = None,
        completeness: float | None = None,
        answer_verified: bool | None = None,
    ) -> ComplianceLog:
        """
        answer_verified is False when the answer-quality gate rejected
        the agent's answer and replaced it (S5), True when it accepted
        it, None when no gate evaluation ran.
        """

        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=ActorTypeEnum.AGENT,
            event_type=ComplianceEventTypeEnum.AGENT_DECISION,
            conversation_id=conversation_id,
            agent_id=agent_id,
            payload={
                "decision_type": decision_type,
                "groundedness": groundedness,
                "relevance": relevance,
                "completeness": completeness,
                "answer_verified": answer_verified,
            },
        )

    async def record_guardrail_fired(
        self,
        *,
        request_id: UUID,
        user_id: str,
        tenant_id: str,
        conversation_id: str | None,
        action: str,
        detection_count: int,
        categories: Sequence[str],
        harmful: bool,
        harmful_category: str | None = None,
    ) -> ComplianceLog:
        """
        Never carries the matched PII substring or the flagged
        response content -- category/action/count only.
        """

        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            # ActorTypeEnum has no SYSTEM member (only USER/AGENT) --
            # the guardrail runs as part of the system's own response
            # pipeline, not a human's action, so AGENT is the closer
            # existing fit; reusing the existing enum per this
            # project's convention rather than extending it for one
            # new call site.
            actor_type=ActorTypeEnum.AGENT,
            event_type=ComplianceEventTypeEnum.GUARDRAIL_FIRED,
            conversation_id=conversation_id,
            payload={
                "action": action,
                "detection_count": detection_count,
                "categories": list(categories),
                "harmful": harmful,
                "harmful_category": harmful_category,
            },
        )

    async def record_hitl_approval_decision(
        self,
        *,
        user_id: str,
        tenant_id: str,
        agent_action_id: str,
        approval_id: str,
        decision_type: str,
        request_id: UUID | None = None,
    ) -> ComplianceLog:
        """
        A thin pointer into the real HITL record -- agent_actions and
        approvals stay the source of truth for the decision's full
        detail (reason, edited payload, ...); this row only anchors
        that decision into the unified compliance timeline.

        request_id is optional here, unlike every other record_*()
        method: a human decision can arrive in a follow-up API call
        well after the request that proposed the gated action, and the
        caller (ApprovalLifecycleService) does not otherwise need to
        fetch that original request_id -- agent_action_id/approval_id
        (resource_id/payload) remain the reliable correlation keys for
        this event type regardless of whether request_id is known.
        """

        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=ActorTypeEnum.USER,
            event_type=ComplianceEventTypeEnum.HITL_APPROVAL_DECISION,
            resource_type="agent_action",
            resource_id=agent_action_id,
            payload={
                "agent_action_id": agent_action_id,
                "approval_id": approval_id,
                "decision_type": decision_type,
            },
        )

    async def record_memory_operation(
        self,
        *,
        user_id: str,
        tenant_id: str,
        operation: UserMemoryOperationEnum,
        actor_type: ActorTypeEnum,
        memory_id: str | None = None,
        content_hash: str | None = None,
        kind: str | None = None,
        count: int | None = None,
        request_id: UUID | None = None,
        conversation_id: str | None = None,
        conversation_event_id: str | None = None,
    ) -> ComplianceLog:
        """
        A change to, or use of, a user's long-term memory.

        Identifiers, counts and a content hash only. This method takes
        no free-text parameter on purpose: memory text is user data
        that must stay erasable, and this table is insert-only and
        retained indefinitely by default, so text logged here could
        never be removed. ``content_hash`` (sha256 of the normalized
        content) is enough to prove which fact was involved without
        storing it.
        """

        payload: dict[str, Any] = {"operation": operation.value}

        for key, value in (
            ("memory_id", memory_id),
            ("content_hash", content_hash),
            ("kind", kind),
            ("count", count),
        ):
            if value is not None:
                payload[key] = value

        return await self._record(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=actor_type,
            event_type=ComplianceEventTypeEnum.MEMORY_OPERATION,
            conversation_id=conversation_id,
            conversation_event_id=conversation_event_id,
            resource_type="user_memory",
            resource_id=memory_id,
            payload=payload,
        )

    async def purge_older_than(
        self,
        *,
        retention_days: int | None,
    ) -> int:
        """
        Permanently delete compliance_log rows older than
        retention_days. Returns the number of rows deleted.

        Refuses outright (raises ValueError, deletes nothing) when
        retention_days is None -- the default (config.compliance.
        ComplianceSettings.COMPLIANCE_LOG_RETENTION_DAYS) means "retain
        indefinitely," and there is no implicit fallback number here.
        A caller must pass a real, explicitly-configured value for
        this to do anything at all.

        Never called automatically anywhere in this codebase: no
        scheduled job, no cron, no background task references this
        method. It exists to be invoked explicitly and deliberately --
        see scripts/python/purge_compliance_log.py -- only once an
        actual retention period has been confirmed against real
        legal/compliance requirements for the relevant jurisdiction
        and matter types, never guessed at here.

        Destructive and irreversible: a real DELETE (see
        ComplianceLogRepository.delete_older_than()), not a soft
        delete or archive. Flushes only, like every other write on
        this service -- the caller controls the commit, so a script
        invoking this can inspect the returned count before deciding
        whether to commit or roll back.
        """

        if retention_days is None:
            raise ValueError(
                "COMPLIANCE_LOG_RETENTION_DAYS is not set (None = retain "
                "indefinitely) -- refusing to purge. This must be set "
                "explicitly, only after confirming a real legal/compliance "
                "retention requirement, before this method will do anything.",
            )

        if retention_days <= 0:
            raise ValueError(
                f"retention_days must be a positive integer, got {retention_days}.",
            )

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        deleted_count = await self._repository.delete_older_than(cutoff=cutoff)

        logger.warning(
            "Compliance log purge executed.",
            extra={
                "operation": "compliance_log_purge",
                "retention_days": retention_days,
                "cutoff": cutoff.isoformat(),
                "deleted_count": deleted_count,
            },
        )

        return deleted_count

    async def _record(
        self,
        *,
        request_id: UUID | None,
        user_id: str,
        tenant_id: str,
        actor_type: ActorTypeEnum,
        event_type: ComplianceEventTypeEnum,
        payload: dict[str, Any],
        conversation_id: str | None = None,
        conversation_event_id: str | None = None,
        thread_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        agent_id: str | None = None,
    ) -> ComplianceLog:
        entry = ComplianceLog(
            request_id=request_id,
            conversation_id=conversation_id,
            conversation_event_id=conversation_event_id,
            thread_id=thread_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=actor_type,
            event_type=event_type,
            payload=payload,
            resource_type=resource_type,
            resource_id=resource_id,
            agent_id=agent_id,
        )

        persisted = await self._repository.create(entry)

        logger.debug(
            "Compliance log entry recorded.",
            extra={
                "operation": "compliance_log_record",
                "event_type": event_type.value,
                "request_id": str(request_id),
                "user_id": user_id,
            },
        )

        return persisted


class StandaloneComplianceLogWriter:
    """
    Self-contained-session compliance log writer for callers with no
    request-scoped AsyncSession -- see this module's docstring.

    Only exposes the record_*() methods AIOrchestrator/
    AgentContinuationService actually need (plan/retrieval/tool-call/
    agent-decision/guardrail); request/response are ChatService's
    concern (it owns the request-scoped session and the surrounding
    transaction, so those two use ComplianceLogService directly, same
    commit as the conversation_event writes).
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def record_plan_created(self, **kwargs: Any) -> None:
        await self._run(lambda service: service.record_plan_created(**kwargs))

    async def record_retrieval_performed(self, **kwargs: Any) -> None:
        await self._run(lambda service: service.record_retrieval_performed(**kwargs))

    async def record_tool_call_executed(self, **kwargs: Any) -> None:
        await self._run(lambda service: service.record_tool_call_executed(**kwargs))

    async def record_agent_decision(self, **kwargs: Any) -> None:
        await self._run(lambda service: service.record_agent_decision(**kwargs))

    async def record_guardrail_fired(self, **kwargs: Any) -> None:
        await self._run(lambda service: service.record_guardrail_fired(**kwargs))

    async def record_memory_operation(self, **kwargs: Any) -> None:
        await self._run(lambda service: service.record_memory_operation(**kwargs))

    async def _run(
        self,
        call: Callable[[ComplianceLogService], Any],
    ) -> None:
        # Local imports: avoids a hard import-time dependency from this
        # always-loaded module onto the repository module for callers
        # that only ever use the request-scoped ComplianceLogService.
        from adapters.persistence.sqlalchemy.repositories.compliance_log import (
            ComplianceLogRepository,
        )

        try:
            async with self._session_factory() as session:
                service = ComplianceLogService(
                    session=session,
                    repository=ComplianceLogRepository(session=session),
                )
                await call(service)
                await session.commit()

        except Exception:
            # Compliance logging must never take down the request it is
            # observing -- a write failure here is logged and swallowed,
            # same "never blocks the response" stance UsageService.record
            # already takes for usage accounting.
            logger.exception(
                "Standalone compliance log write failed.",
                extra={"operation": "compliance_log_record_standalone"},
            )
