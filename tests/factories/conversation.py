"""
Conversation factory.
"""

from __future__ import annotations

import factory

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from src.core.datetime import utcnow
from src.db.mixins import generate_prefixed_uuid_pk
from src.db.models.conversation import Conversation
from tests.factories.base import BaseFactory
from tests.factories.user import UserFactory


class ConversationFactory(BaseFactory):
    """
    Factory for Conversation ORM model.
    """

    class Meta:
        model = Conversation

    class Params:
        """
        Reusable factory traits.
        """

        archived = factory.Trait(
            deleted_at=factory.LazyFunction(
                utcnow,
            ),
        )

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("conv"),
    )

    title = DEFAULT_CONVERSATION_TITLE

    user = factory.SubFactory(
        UserFactory,
    )
    user_id = factory.SelfAttribute("user.id")
