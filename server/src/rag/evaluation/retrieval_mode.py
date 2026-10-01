"""
Retrieval-mode checking for the offline golden-set evaluation.

HybridRetriever degrades instead of failing when one component fails
(review R4): embeddings or vector store down -> keyword-only, keyword
store down -> vector-only, reranker down -> the fused order. That's right
for users, but it hides a broken evaluation: with the embedding model
unreachable, the eval silently measures keyword-only search and still
reports a pass rate.

ModeCheckedRetriever builds a HybridRetriever over recording wrappers of
its four components, works out the mode each search actually ran in, and
raises RetrievalModeError, naming the underlying exception, as soon as
that isn't the requested mode. The degraded modes are evaluated by
disabling one component on purpose (it raises ComponentDisabledError
without being called), never by relying on a real failure.

This module is evaluation-only: the production retriever is unchanged.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, cast, get_args

from core.exceptions.rag import RAGError, RetrievalUnavailableError
from rag.hybrid_retriever import HybridRetriever

if TYPE_CHECKING:
    from rag.models import RetrievalResult
    from rag.protocols.embedding_provider import EmbeddingProviderProtocol
    from rag.protocols.keyword import KeywordStoreProtocol
    from rag.protocols.reranker import RerankerProtocol
    from rag.protocols.vector import VectorStoreProtocol

EvalMode = Literal["full", "keyword_only", "no_rerank"]
EVAL_MODES: tuple[str, ...] = get_args(EvalMode)

Component = Literal["embedding", "vector_store", "keyword_store", "reranker"]

# The component each degraded mode disables.
_DISABLED: dict[str, Component | None] = {
    "full": None,
    "keyword_only": "embedding",
    "no_rerank": "reranker",
}


class RetrievalModeError(RAGError):
    """A search ran in a different retrieval mode than the one requested."""


class ComponentDisabledError(RAGError):
    """A component disabled on purpose to evaluate a degraded mode."""


class _Recorder:
    """The components that failed during the current search."""

    def __init__(self, disabled: Component | None) -> None:
        self.disabled = disabled
        self.failures: dict[Component, BaseException] = {}

    async def call(self, component: Component, method: Any, **kwargs: Any) -> Any:
        if component == self.disabled:
            error = ComponentDisabledError(
                message=f"{component} disabled for this evaluation mode."
            )
            self.failures[component] = error
            raise error
        try:
            return await method(**kwargs)
        except Exception as exc:
            self.failures[component] = exc
            raise


class _Embedding:
    def __init__(self, wrapped: EmbeddingProviderProtocol, recorder: _Recorder) -> None:
        self._wrapped = wrapped
        self._recorder = recorder

    @property
    def metadata(self) -> Any:
        return self._wrapped.metadata

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = await self._recorder.call(
            "embedding", self._wrapped.embed, texts=texts
        )
        return result

    async def embed_one(self, *, text: str) -> list[float]:
        result: list[float] = await self._recorder.call(
            "embedding", self._wrapped.embed_one, text=text
        )
        return result


class _VectorStore:
    def __init__(self, wrapped: VectorStoreProtocol, recorder: _Recorder) -> None:
        self._wrapped = wrapped
        self._recorder = recorder

    async def upsert(self, **kwargs: Any) -> Any:
        return await self._wrapped.upsert(**kwargs)

    async def query(self, **kwargs: Any) -> Any:
        return await self._recorder.call("vector_store", self._wrapped.query, **kwargs)


class _KeywordStore:
    def __init__(self, wrapped: KeywordStoreProtocol, recorder: _Recorder) -> None:
        self._wrapped = wrapped
        self._recorder = recorder

    async def query(self, **kwargs: Any) -> Any:
        return await self._recorder.call("keyword_store", self._wrapped.query, **kwargs)


class _Reranker:
    def __init__(self, wrapped: RerankerProtocol, recorder: _Recorder) -> None:
        self._wrapped = wrapped
        self._recorder = recorder

    async def rerank(self, **kwargs: Any) -> Any:
        return await self._recorder.call("reranker", self._wrapped.rerank, **kwargs)


def _mode_used(failures: Mapping[Component, BaseException], *, unavailable: bool) -> str:
    """The mode HybridRetriever._search() ran in, given what failed."""

    if unavailable:
        return "unavailable"
    if "embedding" in failures or "vector_store" in failures:
        return "keyword_only"
    if "keyword_store" in failures:
        return "vector_only"
    if "reranker" in failures:
        return "no_rerank"
    return "full"


class ModeCheckedRetriever:
    """
    A HybridRetriever that fails unless every search runs in one mode.

    `modes_used` counts the searches by the mode they ran in (only ever
    the requested one: any other raises RetrievalModeError).
    """

    def __init__(self, *, mode: EvalMode, retriever: HybridRetriever, recorder: _Recorder) -> None:
        self.mode = mode
        self.retriever = retriever
        self.modes_used: Counter[str] = Counter()
        self._recorder = recorder

    @classmethod
    def build(
        cls,
        *,
        mode: str,
        embedding_provider: EmbeddingProviderProtocol,
        vector_store: VectorStoreProtocol,
        keyword_store: KeywordStoreProtocol,
        reranker: RerankerProtocol,
        rrf_k: int,
    ) -> ModeCheckedRetriever:
        if mode not in EVAL_MODES:
            raise ValueError(f"Unknown evaluation mode {mode!r}; expected one of {EVAL_MODES}.")

        recorder = _Recorder(disabled=_DISABLED[mode])
        retriever = HybridRetriever(
            embedding_provider=_Embedding(embedding_provider, recorder),
            vector_store=_VectorStore(vector_store, recorder),
            keyword_store=_KeywordStore(keyword_store, recorder),
            reranker=_Reranker(reranker, recorder),
            rrf_k=rrf_k,
        )
        return cls(mode=cast("EvalMode", mode), retriever=retriever, recorder=recorder)

    async def retrieve(self, *, query: str, top_k: int) -> list[RetrievalResult]:
        self._recorder.failures = {}
        unavailable: RetrievalUnavailableError | None = None
        results: list[RetrievalResult] = []

        try:
            results = await self.retriever.retrieve(query=query, top_k=top_k)
        except RetrievalUnavailableError as exc:
            unavailable = exc

        failures = self._recorder.failures
        used = _mode_used(failures, unavailable=unavailable is not None)

        # A search that found no candidates never reaches the reranker, so
        # it can't show the reranker was disabled; it didn't use it either.
        if used == "full" and self.mode == "no_rerank":
            used = "no_rerank"

        if used != self.mode:
            raise self._mismatch(used, failures, unavailable)

        self.modes_used[used] += 1
        return results

    def _mismatch(
        self,
        used: str,
        failures: Mapping[Component, BaseException],
        unavailable: RetrievalUnavailableError | None,
    ) -> RetrievalModeError:
        causes = {
            component: exc
            for component, exc in failures.items()
            if not isinstance(exc, ComponentDisabledError)
        }
        described = "; ".join(
            f"{component}: {type(exc).__name__}: {exc}" for component, exc in causes.items()
        )
        error = RetrievalModeError(
            message=(
                f"Retrieval requested {self.mode} but used {used}"
                + (f" ({described})" if described else "")
                + ". The evaluation doesn't fall back to another mode."
            )
        )
        cause = next(iter(causes.values()), None) or unavailable
        error.__cause__ = cause
        return error


def format_step_summary(
    *,
    mode: str,
    modes_used: Mapping[str, int],
    case_count: int,
    passed_cases: int,
    pass_rate: float,
    mean_scores: Mapping[str, float],
    min_pass_rate: float | None,
) -> str:
    """A Markdown section for one evaluation run (e.g. $GITHUB_STEP_SUMMARY)."""

    queries = sum(modes_used.values())
    used = ", ".join(f"{name} ({count}/{queries} queries)" for name, count in modes_used.items())

    if min_pass_rate is None:
        gate = "not gating"
    else:
        verdict = "passed" if pass_rate * 100 >= min_pass_rate else "failed"
        gate = f"gate {min_pass_rate}%: {verdict}"

    lines = [
        f"### Retrieval eval: `{mode}`",
        "",
        "| | |",
        "|---|---|",
        f"| Mode used | {used or 'none'} |",
        f"| Cases | {passed_cases}/{case_count} passed |",
        f"| Pass rate | {pass_rate:.2%} ({gate}) |",
        *(f"| {name} | {score:.4f} |" for name, score in mean_scores.items()),
        "",
    ]
    return "\n".join(lines) + "\n"
