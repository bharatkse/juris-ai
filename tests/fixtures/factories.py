"""
Factory fixtures.
"""

from __future__ import annotations

import pytest

from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory
from tests.factories.user import UserFactory


@pytest.fixture(autouse=True)
def configure_factories(
    db_session,
):
    """
    Configure all factories with the active database session.
    """

    factories = (
        UserFactory,
        ConversationFactory,
        ConversationEventFactory,
    )

    for factory_class in factories:
        factory_class._meta.sqlalchemy_session = db_session

    yield

    for factory_class in factories:
        factory_class._meta.sqlalchemy_session = None
