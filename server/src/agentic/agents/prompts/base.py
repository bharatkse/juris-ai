"""
Base prompt builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from adapters.observability.logger import get_logger
from agentic.agents.prompts.step_task import render_step_task
from agentic.agents.prompts.token_budget import (
    DEFAULT_RESERVED_OUTPUT_TOKENS,
    fit_to_budget,
)
from agentic.agents.prompts.tool_catalog import render_tool_catalog
from agentic.agents.prompts.user_memory import render_user_memory_block
from core.dto.agent import AgentRequestDTO
from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import MessageRoleEnum
from core.utils.prompt_safety import escape_delimiter

logger = get_logger(__name__)

RETRIEVED_CONTEXT_TAG = "retrieved_context"


class BasePromptBuilder(ABC):
    """
    Base class for agent prompt builders.

    Prompt builders translate an agent-level request and retrieved
    context into a provider-independent LLM request.
    """

    template_name: str

    @abstractmethod
    def build(
        self,
        *,
        request: AgentRequestDTO,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
        model: str,
        reserved_output_tokens: int = DEFAULT_RESERVED_OUTPUT_TOKENS,
    ) -> LLMRequestDTO:
        """
        Build a provider-independent LLM request.

        ``model`` identifies which context window to budget against
        (see agentic.agents.prompts.token_budget) -- callers must pass
        the model that will actually serve this request.
        """

    def load_template(self) -> str:
        """
        Load the prompt template associated with the builder.
        """

        template_path = Path(__file__).parent / "templates" / self.template_name

        return template_path.read_text(
            encoding="utf-8",
        )

    def build_messages(
        self,
        *,
        system_prompt: str,
        request: AgentRequestDTO,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
        model: str,
        reserved_output_tokens: int,
    ) -> tuple[LLMMessageDTO, ...]:
        """
        Assemble system + context + history messages within the
        model's real token budget.

        System instructions are exact and never truncated. History and
        context are trimmed to fit (oldest history first, then
        lowest-scored context) by
        agentic.agents.prompts.token_budget.fit_to_budget -- see there
        for the drop order and its rationale.

        The user's saved memories (``request.conversation.user_memory``)
        are rendered as their own SYSTEM message, never as history, and
        their tokens are reserved by passing them to fit_to_budget
        together with the system prompt: fit_to_budget never trims the
        system side, so it trims history and context to make room for
        the block instead of dropping the block. The one exception is a
        window so small that the block alone leaves no room for any
        history or context; then the block is dropped, with a warning,
        rather than sacrificing the whole conversation for optional
        context.

        The agent's available tools (``request.tool_catalog``) and, when
        there is one, its task for this plan step (``request.instruction``
        / ``request.arguments``) follow the system prompt as their own
        SYSTEM messages, above any evidence. They are part of the agent's
        instructions, so they are reserved with the system prompt and
        never dropped.
        """

        tools_block = render_tool_catalog(request.tool_catalog)
        task_block = render_step_task(
            instruction=request.instruction,
            arguments=request.arguments,
        )
        instructions = "\n\n".join(
            block for block in (system_prompt, tools_block, task_block) if block
        )
        memory_block = render_user_memory_block(request.conversation.user_memory)

        kept_history, kept_context, report = fit_to_budget(
            system_prompt=self._reserve(instructions, memory_block),
            history=request.conversation.messages,
            context=context,
            model=model,
            reserved_output_tokens=reserved_output_tokens,
        )

        if memory_block and report.available_tokens == 0:
            # fit_to_budget reports available_tokens == 0 only when the
            # system side alone overflows the window. Retry without the
            # block; if that still overflows it is the pre-existing
            # configuration error fit_to_budget already logs critically.
            logger.warning(
                "User memory block dropped: system prompt plus memory "
                "leaves no room in the context window for model=%s.",
                model,
            )

            memory_block = ""

            kept_history, kept_context, _report = fit_to_budget(
                system_prompt=instructions,
                history=request.conversation.messages,
                context=context,
                model=model,
                reserved_output_tokens=reserved_output_tokens,
            )

        messages: list[LLMMessageDTO] = [
            LLMMessageDTO(
                role=MessageRoleEnum.SYSTEM,
                content=system_prompt,
            ),
            LLMMessageDTO(
                role=MessageRoleEnum.SYSTEM,
                content=tools_block,
            ),
        ]

        if task_block:
            messages.append(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=task_block,
                ),
            )

        if memory_block:
            messages.append(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=memory_block,
                ),
            )

        if kept_context:
            messages.append(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=self.build_context(
                        context=tuple(kept_context),
                    ),
                ),
            )

        messages.extend(
            LLMMessageDTO(
                role=message.role,
                content=message.content,
            )
            for message in kept_history
        )

        return tuple(messages)

    @staticmethod
    def _reserve(
        system_prompt: str,
        memory_block: str,
    ) -> str:
        """
        The text whose tokens fit_to_budget must treat as
        untouchable: the system prompt plus the memory block that is
        sent alongside it.
        """

        return f"{system_prompt}\n\n{memory_block}" if memory_block else system_prompt

    @staticmethod
    def build_context(
        *,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
    ) -> str:
        """
        Format retrieved content for inclusion in the prompt.

        Wrapped in <retrieved_context> delimiters so the model can tell
        this untrusted, external content apart from the system prompt's
        own instructions -- see the "Untrusted Retrieved Content"
        section of the agent's template, which tells the model how to
        treat text inside these tags. Content sources (RAG retrieval,
        web search, tool output) are not author-controlled and may
        contain adversarial instructions, including a fake closing tag,
        so any delimiter inside the content is escaped first.
        """

        body = "\n\n".join(
            escape_delimiter(item.content, RETRIEVED_CONTEXT_TAG)
            for item in context
            if item.content.strip()
        )

        return f"<{RETRIEVED_CONTEXT_TAG}>\n{body}\n</{RETRIEVED_CONTEXT_TAG}>"
