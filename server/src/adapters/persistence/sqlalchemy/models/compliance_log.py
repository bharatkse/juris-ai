"""
Compliance log database model.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON as JSONB
from sqlalchemy import Enum as PgEnum
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin
from core.enums import ActorTypeEnum, ComplianceEventTypeEnum


class ComplianceLog(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    Immutable compliance/legal-discovery audit trail.

    Deliberately separate from OpenTelemetry tracing (debugging/perf,
    sampled and togglable via OTEL_TRACING -- see adapters/observability/
    telemetry.py) and from conversation_events (UI/user-facing chat
    history, subject to conversation deletion). A compliance record
    must never be silently disabled by a tracing flag, and must not be
    coupled to a user's own deletion of their chat history -- see
    application/services/compliance_log.py's module docstring for the
    full design rationale.

    One row per discrete auditable fact (see ComplianceEventTypeEnum),
    not per status -- a single request/turn produces several rows,
    correlated by ``request_id``.

    Insert-only in ORM code: ComplianceLogRepository exposes no
    update(), and delete() exists only as delete_older_than(), which
    backs the explicit, opt-in retention purge (ComplianceLogService.
    purge_older_than() -- never called automatically anywhere).

    DB-level backstop for the same guarantee: migration
    9338dbb3a96f_restrict_compliance_log_to_insert_.py revokes
    UPDATE/DELETE on this table from the application's configured DB
    role, leaving INSERT/SELECT untouched -- see that migration's
    docstring for a confirmed caveat about table ownership/superuser
    roles bypassing REVOKE, and scripts/python/
    verify_compliance_log_privileges.py for a repeatable, automated
    proof the REVOKE itself is correct against a properly-scoped role.
    """

    __tablename__ = "compliance_log"
    _id_prefix = "cplg"

    # ------------------------------------------------------------------
    # Correlation
    # ------------------------------------------------------------------

    # Nullable: every event_type except HITL_APPROVAL_DECISION always
    # has a real originating request_id at its call site and always
    # supplies one -- see ComplianceLogService's typed record_*()
    # methods. HITL_APPROVAL_DECISION is the one exception: a human
    # decision can arrive in a follow-up API call well after (and
    # structurally separate from) the request that first proposed the
    # gated action, and resolving the original request_id there would
    # need an extra DB fetch this integration doesn't make -- see
    # ApprovalLifecycleService's compliance write. agent_action_id/
    # approval_id (in payload/resource_id) remain the reliable
    # correlation keys for that event type regardless.
    request_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        index=True,
    )

    conversation_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    conversation_event_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    thread_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Accountability
    # ------------------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Same convention as agent_actions.tenant_id: no real multi-tenant
    # column exists upstream today (see agentic/execution/session.py,
    # which sets tenant_id=user_id) -- carried here for the same
    # reason it's carried there, ready for when that changes.
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    actor_type: Mapped[ActorTypeEnum] = mapped_column(
        PgEnum(
            ActorTypeEnum,
            name="actor_type",
        ),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # What happened
    # ------------------------------------------------------------------

    event_type: Mapped[ComplianceEventTypeEnum] = mapped_column(
        PgEnum(
            ComplianceEventTypeEnum,
            name="compliance_event_type",
        ),
        nullable=False,
        index=True,
    )

    # Shape depends on event_type -- see ComplianceEventTypeEnum's
    # docstring and ComplianceLogService for what each type's payload
    # holds and, critically, must never hold (raw message/response
    # text, retrieved chunk text, matched PII substrings).
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Denormalized for cheap filtering without inspecting payload JSON.
    resource_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        index=True,
    )

    agent_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Indexes
    #
    # ix_compliance_log_user_created is the one the core discovery
    # query needs ("everything the system knew/decided for user X
    # between date A and B") -- a single indexed scan, no joins.
    # ------------------------------------------------------------------

    __table_args__ = (
        Index(
            "ix_compliance_log_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_compliance_log_conversation_created",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_compliance_log_event_type_created",
            "event_type",
            "created_at",
        ),
    )
