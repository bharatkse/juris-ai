"""
Unit tests for BasePromptBuilder.build_messages()'s handling of the
<user_memory> block: it must be reserved alongside the system prompt
(never trimmed by fit_to_budget, never carried in history), and history/
context must give way to make room for it instead.
"""

from __future__ import annotations

from agentic.agents.prompts.legal import LegalPromptBuilder
from agentic.agents.prompts.token_budget import (
    DEFAULT_RESERVED_OUTPUT_TOKENS,
    MODEL_CONTEXT_WINDOWS,
    context_window_for,
    count_tokens,
)
from core.dto.agent import AgentRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.dto.tool import RetrievedContentDTO
from core.dto.user_memory import UserMemoryContextItem
from core.enums import (
    GroqModelEnum,
    MessageRoleEnum,
    RetrievalSourceEnum,
    UserMemoryKindEnum,
)
from tests.builders.agentic.agent import build_agent_context

MODEL = GroqModelEnum.LLAMA_3_1_8B

MEMORY = (
    UserMemoryContextItem(
        id="umem_" + "a" * 32,
        kind=UserMemoryKindEnum.PREFERENCE,
        content="Prefers concise answers",
    ),
)


def _request(
    *,
    messages: tuple[MessageDTO, ...],
    user_memory: tuple[UserMemoryContextItem, ...] = (),
) -> AgentRequestDTO:
    return AgentRequestDTO(
        conversation=ConversationDTO(messages=messages, user_memory=user_memory),
        instruction="Answer the user's question.",
        context=build_agent_context(),
    )


def _history(n: int, *, content: str = "message") -> tuple[MessageDTO, ...]:
    return tuple(MessageDTO(role=MessageRoleEnum.USER, content=f"{content} {i}") for i in range(n))


def test_no_memory_produces_no_extra_message() -> None:
    builder = LegalPromptBuilder()

    messages = builder.build_messages(
        system_prompt="You are a legal assistant.",
        request=_request(messages=_history(1)),
        context=(),
        model=MODEL,
        reserved_output_tokens=DEFAULT_RESERVED_OUTPUT_TOKENS,
    )

    assert not any("<user_memory>" in message.content for message in messages)


def test_memory_is_its_own_system_message_before_context_and_history() -> None:
    builder = LegalPromptBuilder()

    context = (
        RetrievedContentDTO(
            content="Section 1 says...",
            source=RetrievalSourceEnum.DOCUMENT,
            source_name="act.pdf",
            score=0.9,
        ),
    )

    messages = builder.build_messages(
        system_prompt="You are a legal assistant.",
        request=_request(messages=_history(1), user_memory=MEMORY),
        context=context,
        model=MODEL,
        reserved_output_tokens=DEFAULT_RESERVED_OUTPUT_TOKENS,
    )

    roles_and_markers = [
        (
            message.role,
            message.content.startswith("## Available tools"),
            message.content.startswith("## Task for this step"),
            "<user_memory>" in message.content,
            "<retrieved_context>" in message.content,
        )
        for message in messages
    ]

    # system prompt, available tools, task for this step, memory block,
    # retrieved context, then history.
    assert roles_and_markers[0] == (MessageRoleEnum.SYSTEM, False, False, False, False)
    assert roles_and_markers[1] == (MessageRoleEnum.SYSTEM, True, False, False, False)
    assert roles_and_markers[2] == (MessageRoleEnum.SYSTEM, False, True, False, False)
    assert roles_and_markers[3] == (MessageRoleEnum.SYSTEM, False, False, True, False)
    assert roles_and_markers[4] == (MessageRoleEnum.SYSTEM, False, False, False, True)
    assert messages[-1].role is MessageRoleEnum.USER


def test_memory_is_never_carried_in_a_history_message() -> None:
    builder = LegalPromptBuilder()

    messages = builder.build_messages(
        system_prompt="You are a legal assistant.",
        request=_request(messages=_history(1), user_memory=MEMORY),
        context=(),
        model=MODEL,
        reserved_output_tokens=DEFAULT_RESERVED_OUTPUT_TOKENS,
    )

    history_messages = [m for m in messages if m.role is MessageRoleEnum.USER]

    assert all("Prefers concise answers" not in m.content for m in history_messages)


def test_memory_survives_history_being_trimmed_to_fit_the_budget() -> None:
    """
    A big enough history to force fit_to_budget to drop messages must
    lose history, not the memory block -- because the block's tokens
    were reserved alongside the system prompt before history was fit.
    """

    builder = LegalPromptBuilder()

    window = context_window_for(MODEL)
    reserved_output = DEFAULT_RESERVED_OUTPUT_TOKENS
    # Comfortably larger than the whole remaining window once system
    # prompt, memory and reserved output are accounted for.
    big_message = "filler word " * 20_000

    messages = builder.build_messages(
        system_prompt="You are a legal assistant.",
        request=_request(
            messages=(MessageDTO(role=MessageRoleEnum.USER, content=big_message),) * 5,
            user_memory=MEMORY,
        ),
        context=(),
        model=MODEL,
        reserved_output_tokens=reserved_output,
    )

    assert any("<user_memory>" in message.content for message in messages)
    assert window > 0  # sanity: a real window was used, not the config-error path


def test_memory_is_dropped_not_truncated_when_the_window_cannot_fit_it_at_all() -> None:
    """
    A pathologically small context window (smaller than the memory
    block plus the fixed system prompt) drops the block entirely,
    with the rest of the prompt still built -- never silently
    truncates the block's own content.
    """

    builder = LegalPromptBuilder()

    huge_memory = (
        UserMemoryContextItem(
            id="umem_" + "b" * 32,
            kind=UserMemoryKindEnum.PREFERENCE,
            content="x" * 4000,
        ),
    )

    tiny_model = "not-a-configured-model"
    assert tiny_model not in MODEL_CONTEXT_WINDOWS  # uses DEFAULT_CONTEXT_WINDOW (8192)

    messages = builder.build_messages(
        system_prompt="You are a legal assistant.",
        request=_request(messages=_history(1), user_memory=huge_memory),
        context=(),
        model=tiny_model,
        # Leave (almost) nothing for anything else.
        reserved_output_tokens=8_000,
    )

    assert not any("<user_memory>" in message.content for message in messages)
    # The system prompt itself is still there, uncut.
    assert messages[0].content == "You are a legal assistant."


def test_memory_block_token_cost_is_what_gets_reserved() -> None:
    """
    Sanity check tying this test file to the same token accounting the
    service's own cap (USER_MEMORY_MAX_PROMPT_TOKENS) relies on:
    count_tokens on the rendered block, not an estimate of the raw
    content.
    """

    from agentic.agents.prompts.user_memory import render_user_memory_block

    block = render_user_memory_block(MEMORY)

    assert count_tokens(block) > 0
