"""
Base prompt builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from agentic.agents.prompts.token_budget import (
    DEFAULT_RESERVED_OUTPUT_TOKENS,
    fit_to_budget,
)
from core.dto.agent import AgentRequestDTO
from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import MessageRoleEnum


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
        """

        kept_history, kept_context, _report = fit_to_budget(
            system_prompt=system_prompt,
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
        ]

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
        contain adversarial instructions.
        """

        body = "\n\n".join(item.content for item in context if item.content.strip())

        return f"<retrieved_context>\n{body}\n</retrieved_context>"
