"""
Tests for planning prompt construction.
"""

from __future__ import annotations

from src.core.dto.clients.llm import LLMRequestDTO
from src.core.dto.planning import PlanningRequestDTO
from src.core.enums import MessageRoleEnum
from src.planning.prompts.planning import PlanningPromptBuilder


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
