"""
High-level builders for common test scenarios.

Builders compose multiple ORM factories into reusable object graphs.
"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.persistence.sqlalchemy.models.conversation import Conversation
from adapters.persistence.sqlalchemy.models.conversation_event import ConversationEvent
from core.enums import MessageRoleEnum
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory


@dataclass(slots=True)
class ChatExchange:
    """
    Represents a single user/assistant interaction.
    """

    conversation: Conversation
    user_event: ConversationEvent
    assistant_event: ConversationEvent


@dataclass(slots=True)
class ConversationScenario:
    """
    Represents a conversation and its associated events.
    """

    conversation: Conversation
    events: list[ConversationEvent]


@dataclass(slots=True)
class ChatConversation:
    """
    Represents a conversation containing a single user message.

    This scenario is commonly used by ChatService tests before an
    assistant response has been generated.
    """

    conversation: Conversation
    user_event: ConversationEvent


def build_chat_conversation(
    *,
    conversation: Conversation | None = None,
    question: str = "Hello",
) -> ChatConversation:
    """
    Build a conversation with a single user message.
    """

    conversation = conversation or ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation=conversation,
        role=MessageRoleEnum.USER,
        content=question,
    )

    return ChatConversation(
        conversation=conversation,
        user_event=user_event,
    )


def build_chat_exchange(
    *,
    conversation: Conversation | None = None,
    question: str = "Hello",
    answer: str = "Hi! How can I help you?",
) -> ChatExchange:
    """
    Build a single user → assistant interaction.
    """

    conversation = conversation or ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation=conversation,
        role=MessageRoleEnum.USER,
        content=question,
    )

    assistant_event = ConversationEventFactory.build(
        conversation=conversation,
        role=MessageRoleEnum.ASSISTANT,
        parent_event=user_event,
        content=answer,
    )

    return ChatExchange(
        conversation=conversation,
        user_event=user_event,
        assistant_event=assistant_event,
    )


def build_conversation_history(
    *,
    conversation: Conversation | None = None,
    turns: int = 3,
) -> ConversationScenario:
    """
    Build a conversation containing multiple user/assistant turns.
    """

    conversation = conversation or ConversationFactory.build()

    events: list[ConversationEvent] = []

    for turn in range(1, turns + 1):
        user_event = ConversationEventFactory.build(
            conversation=conversation,
            role=MessageRoleEnum.USER,
            content=f"Question {turn}",
        )

        assistant_event = ConversationEventFactory.build(
            conversation=conversation,
            role=MessageRoleEnum.ASSISTANT,
            parent_event=user_event,
            content=f"Answer {turn}",
        )

        events.extend(
            [
                user_event,
                assistant_event,
            ]
        )

    return ConversationScenario(
        conversation=conversation,
        events=events,
    )


def build_regenerated_response(
    *,
    conversation: Conversation | None = None,
    question: str = "Explain Article 21.",
    first_answer: str = "First answer.",
    regenerated_answer: str = "Improved answer.",
) -> ConversationScenario:
    """
    Build a conversation where a user message has multiple assistant
    responses.

    This represents a regenerated response scenario.
    """

    conversation = conversation or ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation=conversation,
        role=MessageRoleEnum.USER,
        content=question,
    )

    assistant_event = ConversationEventFactory.build(
        conversation=conversation,
        role=MessageRoleEnum.ASSISTANT,
        parent_event=user_event,
        content=first_answer,
    )

    regenerated_event = ConversationEventFactory.build(
        conversation=conversation,
        role=MessageRoleEnum.ASSISTANT,
        parent_event=user_event,
        content=regenerated_answer,
    )

    return ConversationScenario(
        conversation=conversation,
        events=[
            user_event,
            assistant_event,
            regenerated_event,
        ],
    )
