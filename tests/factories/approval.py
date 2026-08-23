"""
Approval factory.
"""

from __future__ import annotations

from datetime import UTC, datetime

import factory

from src.core.enums import ApprovalStatusEnum
from src.db.mixins import generate_prefixed_uuid_pk
from src.db.models.approval import Approval
from tests.factories.agent_action import AgentActionFactory
from tests.factories.base import BaseFactory
from tests.factories.user import UserFactory


class ApprovalFactory(BaseFactory):
    """
    Factory for Approval ORM model.
    """

    class Meta:
        model = Approval

    class Params:
        """
        Reusable factory traits.
        """

        pending = factory.Trait(
            status=ApprovalStatusEnum.WAITING,
        )

        approved = factory.Trait(
            status=ApprovalStatusEnum.APPROVED,
        )

        rejected = factory.Trait(
            status=ApprovalStatusEnum.REJECTED,
        )

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("appr"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    agent_action = factory.SubFactory(
        AgentActionFactory,
    )

    agent_action_id = factory.SelfAttribute(
        "agent_action.id",
    )

    requester = factory.SubFactory(
        UserFactory,
    )

    requested_by = factory.SelfAttribute(
        "requester.id",
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    status = ApprovalStatusEnum.WAITING

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    approved_by = None
    decision_type = None
    decision_reason = None

    # ------------------------------------------------------------------
    # Edited action
    # ------------------------------------------------------------------

    edited_payload = None
    edited_fingerprint = None

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    expires_at = factory.LazyFunction(
        lambda: datetime.now(UTC),
    )

    decided_at = None
