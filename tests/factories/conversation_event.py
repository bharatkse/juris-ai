"""
Conversation event factory.
"""

from __future__ import annotations

from uuid import uuid4

import factory

from src.core.enums import MessageRoleEnum
from src.db.mixins import generate_prefixed_uuid_pk
from src.db.models.conversation_event import ConversationEvent
from tests.factories.base import BaseFactory
from tests.factories.conversation import ConversationFactory


class ConversationEventFactory(BaseFactory):
    """
    Factory for ConversationEvent ORM model.
    """

    class Meta:
        model = ConversationEvent

    class Params:
        """
        Reusable factory traits.
        """

        user_message = factory.Trait(
            role=MessageRoleEnum.USER,
        )

        assistant_message = factory.Trait(
            role=MessageRoleEnum.ASSISTANT,
        )

        system_message = factory.Trait(
            role=MessageRoleEnum.SYSTEM,
        )

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("evnt"),
    )

    conversation = factory.SubFactory(
        ConversationFactory,
    )

    conversation_id = factory.SelfAttribute(
        "conversation.id",
    )

    request_id = factory.LazyFunction(
        uuid4,
    )

    parent_event = None

    role = MessageRoleEnum.USER

    content = factory.Faker(
        "sentence",
    )

    event_metadata = factory.LazyFunction(
        dict,
    )
