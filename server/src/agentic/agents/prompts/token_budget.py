"""
Token budgeting and truncation for agent prompts.

Token counting
--------------
There is no single, ungated, offline tokenizer that exactly matches
every model this app can route to: Groq serves Llama-3.x and
OpenAI-gpt-oss models, the local provider serves Qwen3 -- three
different vocabularies, none of them cl100k_base (GPT-4's tokenizer).
Llama's own tokenizer files are gated behind a Hugging Face license
acceptance; bundling and matching a separate exact tokenizer per model
family is real work for a token *budget* (a safety margin, not an
exact bill) that doesn't need to be worth it here.

cl100k_base (via tiktoken, already resolvable in this environment) is
used as the approximation: it's a real BPE tokenizer, not a chars/4
heuristic, and is the standard fallback used across the industry when
an exact match isn't available. It's known to generally undercount
relative to Llama-family tokenizers on English text (Llama's BPE merges
are less aggressive) -- SAFETY_MARGIN_RATIO below compensates for that
by inflating every count rather than budgeting to the exact edge. This
has NOT been empirically measured against this app's actual traffic;
treat it as a documented approximation, not a guarantee.

Context windows
----------------
Sourced from provider documentation, not measured here (see
MODEL_CONTEXT_WINDOWS). Qwen3's local entries deliberately do NOT use
Qwen3's native 32K window -- see the comment there for why.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from adapters.clients.llm.local import QWEN3_NUM_CTX
from adapters.observability.logger import get_logger
from core.dto.message import MessageDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import GroqModelEnum, LLMMODELEnum

logger = get_logger(__name__)

_ENCODING_NAME = "cl100k_base"

# See module docstring: cl100k_base tends to undercount Llama-family
# tokens on English text. Treat every counted token as this much more.
SAFETY_MARGIN_RATIO = 0.20

# Context windows sourced from provider documentation (Groq's model
# card pages, as of this writing), not measured against this app's
# actual traffic.
#
# The Qwen3 (local/Ollama) entries use QWEN3_NUM_CTX -- the same
# constant adapters/clients/llm/local.py now explicitly passes as
# Ollama's num_ctx request option, so this registry can never silently
# drift from what's actually requested. Previously this used Ollama's
# own bare default (2048) because local.py never set num_ctx at all;
# now that it does (Qwen3's real native window), the budget matches
# what's actually served.
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    GroqModelEnum.LLAMA_3_1_8B: 131_072,
    GroqModelEnum.LLAMA_3_3_70B: 131_072,
    GroqModelEnum.GPT_OSS_120B: 131_072,
    GroqModelEnum.GPT_OSS_20B: 131_072,
    LLMMODELEnum.QWEN3_4B: QWEN3_NUM_CTX,
    LLMMODELEnum.QWEN3_8B: QWEN3_NUM_CTX,
}

# Conservative fallback for a model string this registry doesn't
# recognize (e.g. a newly configured model not yet added above).
DEFAULT_CONTEXT_WINDOW = 8_192

# Used when the caller doesn't know the task's resolved
# max_output_tokens yet at prompt-build time (see BaseAgent._reason,
# which builds the prompt before resolving the full InferencePolicy).
DEFAULT_RESERVED_OUTPUT_TOKENS = 2_048

# Fixed headroom below the theoretical available budget, independent
# of SAFETY_MARGIN_RATIO's per-token inflation -- covers per-message
# formatting overhead (role markers, separators) that raw content
# token-counting doesn't capture.
FIXED_SAFETY_MARGIN_TOKENS = 256


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING_NAME)


def count_tokens(text: str) -> int:
    """Raw cl100k_base token count for ``text`` (0 for empty/blank)."""

    if not text:
        return 0

    return len(_encoding().encode(text))


def estimate_tokens(text: str) -> int:
    """count_tokens() inflated by SAFETY_MARGIN_RATIO -- use this for
    budgeting decisions, not count_tokens() directly."""

    return math.ceil(count_tokens(text) * (1 + SAFETY_MARGIN_RATIO))


def context_window_for(model: str) -> int:
    """Return the configured context window for ``model``, or
    DEFAULT_CONTEXT_WINDOW if the model isn't in the registry."""

    window = MODEL_CONTEXT_WINDOWS.get(model)

    if window is None:
        logger.warning(
            "No configured context window for model '%s'; using the "
            "conservative default of %d tokens.",
            model,
            DEFAULT_CONTEXT_WINDOW,
        )
        return DEFAULT_CONTEXT_WINDOW

    return window


@dataclass(frozen=True, slots=True)
class TruncationReport:
    """What fit_to_budget() actually had to drop, if anything."""

    history_messages_dropped: int
    context_items_dropped: int
    available_tokens: int
    used_tokens: int

    @property
    def truncated(self) -> bool:
        return self.history_messages_dropped > 0 or self.context_items_dropped > 0


def fit_to_budget(
    *,
    system_prompt: str,
    history: Sequence[MessageDTO],
    context: Sequence[RetrievedContentDTO],
    model: str,
    reserved_output_tokens: int = DEFAULT_RESERVED_OUTPUT_TOKENS,
) -> tuple[list[MessageDTO], list[RetrievedContentDTO], TruncationReport]:
    """
    Trim ``history`` and ``context`` to fit the model's real context
    window, never touching ``system_prompt``.

    Drop order when over budget: oldest history first (history is
    assumed chronologically ordered, oldest first -- callers must not
    pass it pre-reversed), then lowest-scored retrieved context items,
    until what remains fits. System instructions are never truncated;
    if the system prompt alone doesn't fit the window (a configuration
    error, not a runtime condition to silently paper over), everything
    else is dropped and a critical log is emitted rather than cutting
    the system prompt.
    """

    window = context_window_for(model)
    system_tokens = estimate_tokens(system_prompt)
    available = window - reserved_output_tokens - system_tokens - FIXED_SAFETY_MARGIN_TOKENS

    if available <= 0:
        logger.critical(
            "System prompt (+reserved output) alone exceeds the model "
            "context window: model=%s window=%d system_tokens=%d "
            "reserved_output_tokens=%d. Dropping all history/context "
            "for this request rather than truncating system "
            "instructions.",
            model,
            window,
            system_tokens,
            reserved_output_tokens,
        )
        return (
            [],
            [],
            TruncationReport(
                history_messages_dropped=len(history),
                context_items_dropped=len(context),
                available_tokens=max(available, 0),
                used_tokens=0,
            ),
        )

    kept_history = list(history)
    # Drop lowest-scored context first: sort ascending by score (None
    # treated as lowest -- an un-scored item has no basis to prefer
    # keeping it over a scored one), pop from the front of that view.
    kept_context = sorted(
        context,
        key=lambda item: (item.score if item.score is not None else float("-inf")),
    )

    def _current_tokens() -> int:
        return sum(estimate_tokens(m.content) for m in kept_history) + sum(
            estimate_tokens(c.content) for c in kept_context
        )

    history_dropped = 0
    context_dropped = 0

    while _current_tokens() > available and kept_history:
        kept_history.pop(0)
        history_dropped += 1

    while _current_tokens() > available and kept_context:
        kept_context.pop(0)
        context_dropped += 1

    # Restore original (retrieval-rank) order for whatever context
    # survived -- the sort above was only to pick a drop order.
    if context_dropped:
        surviving = {id(item) for item in kept_context}
        kept_context = [item for item in context if id(item) in surviving]

    report = TruncationReport(
        history_messages_dropped=history_dropped,
        context_items_dropped=context_dropped,
        available_tokens=available,
        used_tokens=_current_tokens(),
    )

    if report.truncated:
        logger.warning(
            "Prompt truncated to fit token budget: model=%s window=%d "
            "available=%d used=%d history_dropped=%d context_dropped=%d.",
            model,
            window,
            available,
            report.used_tokens,
            history_dropped,
            context_dropped,
        )

    return kept_history, kept_context, report
