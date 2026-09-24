"""
Agent policy persistence model.

Replaces the previously-empty AGENT_POLICIES static dict
(agentic/policy/config.py) as the source of truth for which tools an
agent may use. See application/services -- there is no application
service for this; DatabaseAgentPolicyProvider
(agentic/policy/agent_policy.py) reads this table directly through
AgentPolicyRepository, since policy resolution is a pure read used
inside the agent execution runtime, not an application-layer
orchestration concern.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin


class AgentPolicyModel(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    One agent's tool-access policy.

    allowed_agents/allow_delegation/require_citations (the rest of
    agentic.policy.schemas.AgentPolicy) are not yet columns here --
    every row resolves to allowed_agents=frozenset(), allow_delegation
    =False, require_citations=False regardless of what's stored,
    matching today's actual behavior (delegation/citations were never
    configurable before this table existed either). Only allowed_tools
    is real, DB-backed policy today.
    """

    __tablename__ = "agent_policies"
    _id_prefix = "apol"

    agent_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    allowed_tools: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
