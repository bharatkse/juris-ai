"""
Agent action factory.
"""

from __future__ import annotations

import factory

from src.core.enums import ActionTypeEnum, ActorTypeEnum, AgentActionStatusEnum
from src.db.mixins import generate_prefixed_uuid_pk
from src.db.models.agent_action import AgentAction
from tests.factories.base import BaseFactory
from tests.factories.conversation_event import ConversationEventFactory
from tests.factories.user import UserFactory


class AgentActionFactory(BaseFactory):
    """
    Factory for AgentAction ORM model.
    """

    class Meta:
        model = AgentAction

    class Params:
        """
        Reusable factory traits.
        """

        draft = factory.Trait(
            status=AgentActionStatusEnum.DRAFT,
        )

        executed = factory.Trait(
            status=AgentActionStatusEnum.COMPLETED,
        )

        failed = factory.Trait(
            status=AgentActionStatusEnum.FAILED,
            error="Action execution failed.",
        )

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("actn"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    event = factory.SubFactory(
        ConversationEventFactory,
    )
    conversation_event_id = factory.SelfAttribute(
        "event.id",
    )

    user = factory.SubFactory(
        UserFactory,
    )
    user_id = factory.SelfAttribute(
        "user.id",
    )

    # ------------------------------------------------------------------
    # Execution / traceability
    # ------------------------------------------------------------------

    execution_id = factory.Faker(
        "uuid4",
    )

    thread_id = factory.Faker(
        "uuid4",
    )

    # ------------------------------------------------------------------
    # Accountability / tenancy
    # ------------------------------------------------------------------

    tenant_id = factory.Faker(
        "uuid4",
    )

    # ------------------------------------------------------------------
    # Actor
    # ------------------------------------------------------------------

    actor_type = ActorTypeEnum.USER

    agent_id = factory.Faker(
        "uuid4",
    )

    # ------------------------------------------------------------------
    # Action target
    # ------------------------------------------------------------------

    action_type = ActionTypeEnum.TOOL_CALL

    tool_name = "test_tool"

    target_agent_id = None

    resource_type = None

    resource_id = None

    # ------------------------------------------------------------------
    # Action payload
    # ------------------------------------------------------------------

    parameters = factory.LazyFunction(
        lambda: {
            "input": "test",
        },
    )

    reason = "Test agent action."

    # ------------------------------------------------------------------
    # Action lifecycle
    # ------------------------------------------------------------------

    status = AgentActionStatusEnum.DRAFT

    # ------------------------------------------------------------------
    # Action integrity
    # ------------------------------------------------------------------

    fingerprint = factory.Faker(
        "sha256",
    )

    # ------------------------------------------------------------------
    # Execution result
    # ------------------------------------------------------------------

    result = None

    error = None

    executed_at = None
