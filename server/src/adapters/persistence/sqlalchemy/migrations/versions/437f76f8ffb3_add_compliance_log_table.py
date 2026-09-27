"""add compliance_log table

Revision ID: 437f76f8ffb3
Revises: cd2984cd9ff9
Create Date: 2026-09-14 18:04:29.626291

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "437f76f8ffb3"
down_revision: str | Sequence[str] | None = "cd2984cd9ff9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# "actor_type" already exists (created by 2ceb9121ef13_init_hitl_models);
# create_type=False + checkfirst=True below means this migration never
# tries to redefine it, only reuses it for the new column.
actor_type_enum = postgresql.ENUM(
    "USER",
    "AGENT",
    name="actor_type",
    create_type=False,
)

compliance_event_type_enum = postgresql.ENUM(
    "REQUEST_RECEIVED",
    "RETRIEVAL_PERFORMED",
    "PLAN_CREATED",
    "TOOL_CALL_EXECUTED",
    "AGENT_DECISION",
    "GUARDRAIL_FIRED",
    "HITL_APPROVAL_DECISION",
    "RESPONSE_RETURNED",
    name="compliance_event_type",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    actor_type_enum.create(bind, checkfirst=True)
    compliance_event_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "compliance_log",
        # Nullable -- see ComplianceLog's model docstring: every
        # event_type except HITL_APPROVAL_DECISION always supplies one.
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.String(length=64), nullable=True),
        sa.Column("conversation_event_id", sa.String(length=64), nullable=True),
        sa.Column("thread_id", sa.String(length=128), nullable=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("actor_type", actor_type_enum, nullable=False),
        sa.Column("event_type", compliance_event_type_enum, nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=256), nullable=True),
        sa.Column("agent_id", sa.String(length=128), nullable=True),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compliance_log")),
    )
    op.create_index(
        "ix_compliance_log_conversation_created",
        "compliance_log",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compliance_log_conversation_id"),
        "compliance_log",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compliance_log_event_type"),
        "compliance_log",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_log_event_type_created",
        "compliance_log",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compliance_log_request_id"),
        "compliance_log",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compliance_log_resource_id"),
        "compliance_log",
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compliance_log_tenant_id"),
        "compliance_log",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_log_user_created",
        "compliance_log",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compliance_log_user_id"),
        "compliance_log",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_compliance_log_user_id"), table_name="compliance_log")
    op.drop_index("ix_compliance_log_user_created", table_name="compliance_log")
    op.drop_index(op.f("ix_compliance_log_tenant_id"), table_name="compliance_log")
    op.drop_index(op.f("ix_compliance_log_resource_id"), table_name="compliance_log")
    op.drop_index(op.f("ix_compliance_log_request_id"), table_name="compliance_log")
    op.drop_index("ix_compliance_log_event_type_created", table_name="compliance_log")
    op.drop_index(op.f("ix_compliance_log_event_type"), table_name="compliance_log")
    op.drop_index(op.f("ix_compliance_log_conversation_id"), table_name="compliance_log")
    op.drop_index("ix_compliance_log_conversation_created", table_name="compliance_log")
    op.drop_table("compliance_log")

    # actor_type is NOT dropped -- still owned/used by agent_actions
    # (created in 2ceb9121ef13_init_hitl_models). Only the enum this
    # migration actually introduced is torn down here.
    bind = op.get_bind()
    compliance_event_type_enum.drop(bind, checkfirst=True)
