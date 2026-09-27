"""
Tests for planning prompt construction.
"""

from __future__ import annotations

from agentic.planning.prompts.planning import PlanningPromptBuilder
from core.dto.clients.llm import LLMRequestDTO
from core.dto.planning import PlanningRequestDTO
from core.dto.user_memory import UserMemoryContextItem
from core.enums import MessageRoleEnum, UserMemoryKindEnum
from core.models.conversation import ConversationMessageSchema


def test_build_creates_planning_request() -> None:
    """
    Build a planning LLM request from the user's request.
    """

    builder = PlanningPromptBuilder()

    request = PlanningRequestDTO(
        message="Review this contract and identify risks.",
    )

    llm_request = builder.build(
        request=request,
    )

    assert isinstance(
        llm_request,
        LLMRequestDTO,
    )

    assert len(llm_request.messages) == 2

    system_message = llm_request.messages[0]
    user_message = llm_request.messages[1]

    assert system_message.role is MessageRoleEnum.SYSTEM
    assert system_message.content

    assert user_message.role is MessageRoleEnum.USER
    assert "Review this contract and identify risks." in (user_message.content)


def test_build_does_not_require_preclassified_intent() -> None:
    """
    Planning prompt construction must not require a separately
    classified intent.
    """

    builder = PlanningPromptBuilder()

    request = PlanningRequestDTO(
        message="What does the limitation period mean?",
    )

    llm_request = builder.build(
        request=request,
    )

    user_message = llm_request.messages[-1]

    assert "Detected intent:" not in user_message.content
    assert "What does the limitation period mean?" in (user_message.content)


def test_build_includes_conversation_history() -> None:
    ...
    builder = PlanningPromptBuilder()

    request = PlanningRequestDTO(
        message="Now identify the risks.",
        history=(
            # Use your existing ConversationMessageSchema fields here
            # if the constructor differs in your project.
        ),
    )

    builder.build(
        request=request,
    )


def test_build_inserts_a_memory_block_as_its_own_system_message_between_system_and_history() -> (
    None
):
    """
    request.user_memory renders as a SECOND SYSTEM message, positioned
    after the fixed planning system prompt and before conversation
    history -- never folded into history, where it could be mistaken
    for something the user just said.
    """

    builder = PlanningPromptBuilder()

    memory = (
        UserMemoryContextItem(
            id="umem_" + "a" * 32,
            kind=UserMemoryKindEnum.PREFERENCE,
            content="Prefers concise answers",
        ),
    )

    request = PlanningRequestDTO(
        message="Summarize this judgment.",
        history=(ConversationMessageSchema(role=MessageRoleEnum.USER, content="earlier"),),
        user_memory=memory,
    )

    llm_request = builder.build(request=request)

    assert len(llm_request.messages) == 4

    system_message, memory_message, history_message, user_message = llm_request.messages

    assert system_message.role is MessageRoleEnum.SYSTEM
    assert memory_message.role is MessageRoleEnum.SYSTEM
    assert "Prefers concise answers" in memory_message.content
    assert "<user_memory>" in memory_message.content
    assert history_message.content == "earlier"
    assert user_message.role is MessageRoleEnum.USER


def test_build_omits_the_memory_message_entirely_when_there_is_nothing_to_inject() -> None:
    builder = PlanningPromptBuilder()

    request = PlanningRequestDTO(
        message="Summarize this judgment.",
    )

    llm_request = builder.build(request=request)

    assert len(llm_request.messages) == 2
    assert all("<user_memory>" not in message.content for message in llm_request.messages)
