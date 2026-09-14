"""
Cross-conversation memory.

Folds conversation events older than UNSUMMARIZED_EVENT_LIMIT into a
compact rolling summary (Conversation.rolling_summary) instead of
either replaying an ever-growing raw history or silently discarding
old context. See ChatService._build_chat_request for how the result
is used: the summary is prepended to history in place of the raw
events it replaces, then everything still goes through the token
budget in agentic/agents/prompts/token_budget.py as the final,
model-real-context-window safety net.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from agentic.agents.prompts.token_budget import count_tokens
from application.services.base import BaseService
from config.settings import get_settings
from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.dto.inference import InferencePolicy, LLMTask
from core.enums import MessageRoleEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from adapters.clients.llm.base import LLMClient
    from adapters.persistence.sqlalchemy.models.conversation import (
        Conversation,
    )
    from adapters.persistence.sqlalchemy.models.conversation_event import (
        ConversationEvent,
    )
    from application.services.conversation_event import ConversationEventService

logger = get_logger(__name__)

# Recent events kept verbatim in every prompt; anything older than this
# many unsummarized events gets folded into rolling_summary instead.
#
# This is the "20" that used to be chat.py's hardcoded fetch limit,
# repurposed as the summarization trigger boundary rather than the
# final truncation mechanism -- that job now belongs to the token
# budget in agentic/agents/prompts/token_budget.py, which applies
# regardless of how history got assembled. The two layer: this decides
# WHAT gets folded into prose vs kept verbatim; the token budget
# decides what fits the model actually serving the request.
UNSUMMARIZED_EVENT_LIMIT = 20

# Generous DB-fetch cap so a pathologically long, never-summarized
# conversation doesn't pull unbounded history into memory here. If a
# conversation exceeds this before ever being summarized (only
# possible if summarization has been failing), everything fetched is
# treated as unsummarized and folded in at once.
SUMMARIZATION_FETCH_LIMIT = 500

# Caps the summary's own length so it can only ever consume a bounded,
# known slice of the per-request history budget instead of growing
# unboundedly across a very long conversation and eating further into
# that budget each time it's regenerated.
SUMMARY_MAX_OUTPUT_TOKENS = 512

_SUMMARIZATION_SYSTEM_PROMPT = (
    "You compress conversation history for a legal assistant. Produce a "
    "compact, factual summary of the conversation so far, preserving "
    "concrete facts, decisions, and open questions the user raised. Do "
    "not add commentary, opinions, or information not present in the "
    "conversation. Write plain prose, not a transcript."
)


class ConversationSummarizationService(BaseService):
    """
    Ensures a conversation's unsummarized tail never grows unbounded.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        conversation_event_service: ConversationEventService,
        llm_client: LLMClient,
        inference_policy: InferencePolicy | None = None,
    ) -> None:
        super().__init__(session)
        self._conversation_event_service = conversation_event_service
        self._llm_client = llm_client
        self._inference_policy = inference_policy or InferencePolicy()

    async def ensure_summarized(
        self,
        *,
        conversation: Conversation,
    ) -> Conversation:
        """
        Fold events older than the most recent UNSUMMARIZED_EVENT_LIMIT
        into conversation.rolling_summary, if there's a large-enough
        unsummarized tail to justify it, and persist the result.

        Best-effort: a summarization failure is logged and swallowed --
        callers get a usable (unsummarized-for-now) conversation back
        rather than a broken request.
        """

        events = await self._conversation_event_service.list(
            conversation_id=conversation.id,
            limit=SUMMARIZATION_FETCH_LIMIT,
        )

        unsummarized = self._unsummarized_tail(
            conversation=conversation,
            events=events,
        )

        if len(unsummarized) <= UNSUMMARIZED_EVENT_LIMIT:
            return conversation

        to_fold = unsummarized[:-UNSUMMARIZED_EVENT_LIMIT]
        kept_verbatim = unsummarized[-UNSUMMARIZED_EVENT_LIMIT:]

        try:
            summary = await self._summarize(
                previous_summary=conversation.rolling_summary,
                events=to_fold,
            )

        except Exception:
            logger.exception(
                "Conversation summarization failed; continuing with the "
                "existing (unsummarized or stale) state.",
                extra={"conversation_id": str(conversation.id)},
            )
            return conversation

        conversation.rolling_summary = summary
        conversation.rolling_summary_through_created_at = to_fold[-1].created_at

        await self.flush()
        await self.refresh(conversation)

        logger.info(
            "Folded older event(s) into rolling_summary.",
            extra={
                "conversation_id": str(conversation.id),
                "folded_count": len(to_fold),
                "kept_verbatim_count": len(kept_verbatim),
            },
        )

        return conversation

    @staticmethod
    def _unsummarized_tail(
        *,
        conversation: Conversation,
        events: list[ConversationEvent],
    ) -> list[ConversationEvent]:
        anchor = conversation.rolling_summary_through_created_at

        if anchor is None:
            return events

        # Events fetched in chronological (ascending) order -- everything
        # at or before the boundary has already been folded in.
        return [event for event in events if event.created_at > anchor]

    async def _summarize(
        self,
        *,
        previous_summary: str | None,
        events: list[ConversationEvent],
    ) -> str:
        transcript = "\n".join(f"{event.role.value}: {event.content}" for event in events)

        user_content = (
            f"Previous summary:\n{previous_summary}\n\n" if previous_summary else ""
        ) + f"Conversation to fold in:\n{transcript}"

        # settings.llm.SUMMARIZATION_MODEL, not whatever GROQ_MODEL the
        # client defaults to -- one config point, deliberately easy to
        # revert (see its docstring in config/llm.py: based on a single
        # spot-check, not a calibration).
        summarization_model = get_settings().llm.SUMMARIZATION_MODEL.value

        inference = self._inference_policy.resolve(
            LLMTask.SUMMARIZATION,
            model=summarization_model,
            max_output_tokens=SUMMARY_MAX_OUTPUT_TOKENS,
        )

        request = LLMRequestDTO(
            messages=(
                LLMMessageDTO(
                    role=MessageRoleEnum.SYSTEM,
                    content=_SUMMARIZATION_SYSTEM_PROMPT,
                ),
                LLMMessageDTO(
                    role=MessageRoleEnum.USER,
                    content=user_content,
                ),
            ),
            inference=inference,
        )

        response = await self._llm_client.generate(request=request)
        summary = response.content.strip()

        # Cheap, real signal for whenever a quality complaint surfaces
        # later -- there's no automated summarization-quality harness
        # today (unlike the answer-quality gate's calibration script),
        # so this is the only ongoing visibility into what model
        # produced a given summary and how long it came out.
        logger.info(
            "Conversation summarized.",
            extra={
                "operation": "summarize_conversation",
                "model": summarization_model,
                "summary_tokens": count_tokens(summary),
                "folded_event_count": len(events),
            },
        )

        return summary
