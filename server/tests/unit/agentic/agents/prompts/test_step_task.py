"""
The plan step's instruction and arguments reach the agent's prompt.

Before, AgentExecutionNode copied step.instruction/arguments into the
AgentRequestDTO but no prompt builder rendered either, so every step of a
multi-step plan answered the whole request.
"""

from __future__ import annotations

from agentic.agents.prompts.legal import LegalPromptBuilder
from agentic.agents.prompts.step_task import (
    MAX_ARGUMENTS_CHARS,
    MAX_INSTRUCTION_CHARS,
    STEP_TASK_HEADING,
)
from agentic.agents.prompts.token_budget import DEFAULT_RESERVED_OUTPUT_TOKENS
from agentic.agents.prompts.tool_catalog import TOOL_CATALOG_HEADING
from agentic.execution.graph.nodes import AgentExecutionNode
from core.dto.agent import AgentContextDTO, AgentRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.dto.planning import ExecutionStepDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import AgentTypeEnum, MessageRoleEnum, RetrievalSourceEnum

MODEL = "llama-3.3-70b-versatile"

CONTEXT = AgentContextDTO(user_id="u", execution_id="e", thread_id="t", conversation_event_id="c")
CONVERSATION = ConversationDTO(
    messages=(
        MessageDTO(
            role=MessageRoleEnum.USER,
            content="Summarise section 43 and then list the penalties it sets.",
        ),
    ),
)


def _messages(request: AgentRequestDTO, context=()):
    return (
        LegalPromptBuilder()
        .build(
            request=request,
            context=context,
            model=MODEL,
            reserved_output_tokens=DEFAULT_RESERVED_OUTPUT_TOKENS,
        )
        .messages
    )


def _task_block(request: AgentRequestDTO) -> str | None:
    blocks = [m.content for m in _messages(request) if m.content.startswith(STEP_TASK_HEADING)]
    assert len(blocks) <= 1
    return blocks[0] if blocks else None


def _step(step_id: str, instruction: str, arguments: dict) -> ExecutionStepDTO:
    return ExecutionStepDTO(
        id=step_id,
        agent=AgentTypeEnum.LEGAL,
        instruction=instruction,
        depends_on=(),
        stage=1,
        arguments=arguments,
    )


def _request_for(step: ExecutionStepDTO) -> AgentRequestDTO:
    """The request AgentExecutionNode builds for this plan step."""

    return AgentExecutionNode._build_agent_request(
        state={"conversation": CONVERSATION, "context": CONTEXT},
        step=step,
    )


def test_instruction_and_arguments_are_rendered_below_the_system_prompt_above_evidence() -> None:
    request = _request_for(
        _step(
            "step-1", "Summarise section 43 of the IT Act.", {"act": "IT Act 2000", "section": "43"}
        ),
    )
    evidence = (
        RetrievedContentDTO(
            source=RetrievalSourceEnum.DOCUMENT,
            source_name="it_act",
            content="Section 43 text.",
            score=0.9,
        ),
    )

    messages = _messages(request, context=evidence)
    contents = [message.content for message in messages]

    task_index = next(i for i, c in enumerate(contents) if c.startswith(STEP_TASK_HEADING))
    tools_index = next(i for i, c in enumerate(contents) if c.startswith(TOOL_CATALOG_HEADING))
    evidence_index = next(i for i, c in enumerate(contents) if c.startswith("<retrieved_context>"))

    assert tools_index < task_index < evidence_index
    assert messages[task_index].role is MessageRoleEnum.SYSTEM

    task = contents[task_index]
    assert "Summarise section 43 of the IT Act." in task
    assert 'Arguments: {"act": "IT Act 2000", "section": "43"}' in task
    assert "does not override the instructions above" in task


def test_two_plan_steps_get_different_prompts() -> None:
    summarise = _request_for(_step("step-1", "Summarise section 43.", {}))
    penalties = _request_for(_step("step-2", "List the penalties section 43 sets.", {}))

    summarise_task = _task_block(summarise)
    penalties_task = _task_block(penalties)

    assert "Summarise section 43." in summarise_task
    assert "List the penalties" not in summarise_task
    assert "List the penalties section 43 sets." in penalties_task
    assert _messages(summarise) != _messages(penalties)


def test_no_task_block_without_an_instruction_or_arguments() -> None:
    assert _task_block(_request_for(_step("step-1", "   ", {}))) is None


def test_oversized_instruction_and_arguments_are_capped() -> None:
    task = _task_block(
        _request_for(
            _step(
                "step-1",
                "x" * (MAX_INSTRUCTION_CHARS + 500),
                {"blob": "y" * (MAX_ARGUMENTS_CHARS + 500)},
            ),
        ),
    )

    assert "x" * MAX_INSTRUCTION_CHARS + " [truncated]" in task
    assert "x" * (MAX_INSTRUCTION_CHARS + 1) not in task
    assert task.count("y") < MAX_ARGUMENTS_CHARS
    assert task.endswith("[truncated]")
