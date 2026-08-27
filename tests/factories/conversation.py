"""
Conversation factory.
"""

from __future__ import annotations

import factory

from adapters.persistence.sqlalchemy.mixins import generate_prefixed_uuid_pk
from adapters.persistence.sqlalchemy.models.conversation import Conversation
from core.constants import DEFAULT_CONVERSATION_TITLE
from core.utils.datetime import utcnow
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
