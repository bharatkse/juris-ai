"""
Conversation event factory.
"""

from __future__ import annotations

import factory

from src.core.enums import MessageRole
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
            role=MessageRole.USER,
        )

        assistant_message = factory.Trait(
            role=MessageRole.ASSISTANT,
        )

        system_message = factory.Trait(
            role=MessageRole.SYSTEM,
        )

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("event"),
    )

    conversation = factory.SubFactory(
        ConversationFactory,
    )
    conversation_id = factory.SelfAttribute("conversation.id")
    parent_event = None

    role = MessageRole.USER

    content = factory.Faker(
        "sentence",
    )

    event_metadata = factory.LazyFunction(
        dict,
    )
