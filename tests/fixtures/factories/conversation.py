"""
Conversation fixtures.
"""

from __future__ import annotations

import pytest

from tests.factories.conversation import ConversationFactory
from tests.factories.user import UserFactory


@pytest.fixture
async def conversation(
    user_repository,
    conversation_repository,
):
    """
    Return a persisted conversation.
    """

    user = await user_repository.create(
        UserFactory.build(),
    )

    return await conversation_repository.create(
        ConversationFactory.build(
            user=user,
        ),
    )
