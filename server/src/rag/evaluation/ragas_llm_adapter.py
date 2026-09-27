"""
Adapter from our provider-independent Judge callable to ragas'
BaseRagasLLM contract.

Lets ragas' built-in metrics (e.g. Faithfulness) run against our
existing Groq/local LLM client without ragas needing its own provider
integration for it -- see rag.evaluation.evaluator.Judge for the
callable this wraps.

BaseRagasLLM declares three abstract methods: generate_text (sync),
agenerate_text (async) and, as of ragas 0.4, is_finished. Every ragas metric we use calls the async path
only (PydanticPrompt.generate() -> BaseRagasLLM.generate() ->
agenerate_text -- confirmed by reading ragas' source directly), so
generate_text is implemented only to satisfy the ABC and raises if
ever actually reached.

ragas' own import is deferred to build_judge_ragas_llm() (matching
ragas_offline.py's existing lazy-import pattern), not done at module
level -- importing this module alone must not import ragas or start
its analytics thread. This is also *why* JudgeRagasLLM is built inside
a function rather than defined as a normal module-level class: it
subclasses BaseRagasLLM, and a base class has to be a real object at
class-definition time -- unlike a type hint, that can't be deferred
with TYPE_CHECKING alone.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field
from functools import lru_cache

from langchain_core.outputs import Generation, LLMResult

if t.TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.callbacks import Callbacks
    from langchain_core.prompt_values import PromptValue
    from ragas.llms.base import BaseRagasLLM

    from rag.evaluation.evaluator import Judge


@lru_cache(maxsize=1)
def _judge_ragas_llm_class() -> Callable[..., BaseRagasLLM]:
    """
    Build the JudgeRagasLLM class the first time it's needed.

    Memoized so repeated calls return the same class object rather
    than redefining (and re-importing ragas.llms.base) every time.
    """

    from ragas.llms.base import BaseRagasLLM

    @dataclass
    class JudgeRagasLLM(BaseRagasLLM):
        """
        Thin BaseRagasLLM implementation backed by a single Judge callable.

        judge defaults to None only so this dataclass can subclass
        BaseRagasLLM (whose own fields all have defaults, and dataclass
        field ordering requires that); __post_init__ rejects an actually-
        missing judge immediately rather than failing confusingly on first
        use.

        n > 1 (multiple sampled completions) is answered by duplicating one
        real Judge call's result rather than sampling n times -- our Judge
        is a single-shot callable with no notion of repeated sampling, and
        nothing in this codebase's ragas usage requests n > 1 today.
        """

        judge: Judge | None = field(default=None)

        def __post_init__(self) -> None:
            if self.judge is None:
                raise ValueError("judge is required.")

            super().__post_init__()

        def generate_text(
            self,
            prompt: PromptValue,
            n: int = 1,
            temperature: float = 1e-8,
            stop: list[str] | None = None,
            callbacks: Callbacks = None,
        ) -> LLMResult:
            raise NotImplementedError(
                "JudgeRagasLLM only supports the async path -- ragas metrics "
                "call agenerate_text, never generate_text.",
            )

        async def agenerate_text(
            self,
            prompt: PromptValue,
            n: int = 1,
            temperature: float | None = None,
            stop: list[str] | None = None,
            callbacks: Callbacks = None,
        ) -> LLMResult:
            assert self.judge is not None  # enforced in __post_init__

            response = await self.judge(prompt.to_string())

            return LLMResult(
                generations=[[Generation(text=response) for _ in range(max(n, 1))]],
            )

        def is_finished(self, response: LLMResult) -> bool:
            """
            Always True: our Judge returns only final text, with no
            finish_reason metadata to inspect -- the same answer ragas'
            own LangchainLLMWrapper gives when generation_info is
            absent. Abstract on BaseRagasLLM as of ragas 0.4 (not in
            0.2.15, which this adapter was first written against).
            Returning False would make ragas raise
            LLMDidNotFinishException.
            """

            return True

    return JudgeRagasLLM


def build_judge_ragas_llm(*, judge: Judge) -> BaseRagasLLM:
    """Build a BaseRagasLLM-compatible object backed by a Judge callable."""

    return _judge_ragas_llm_class()(judge=judge)
