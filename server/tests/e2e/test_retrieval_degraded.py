"""
E2E: a chat turn when part of retrieval is down (review R4, G2).

Over real HTTP and Postgres, with the real HybridRetriever, RetrieverTool,
evidence seeding and answer gate. Only the components' own boundaries are
stubbed: the vector and keyword stores (the dev and CI databases hold no
corpus), the reranker model, and -- to take it down -- the embedding
provider. The LLM boundaries are stubbed as elsewhere (planner, agent
reasoning; the groundedness judge by hermetic_llm).

- Reranker down: the fused order is used and the answer is verified.
- Embeddings down: retrieval falls back to keyword search, but the answer
  gate can't score relevance (it uses the same embedding model), so the
  turn ends with the "couldn't verify" answer -- 200, not a 500 (G2).
- Embeddings and keyword store down: nothing can be searched, so the
  "no sources" answer.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from agentic.agents.base import BaseAgent
from agentic.agents.runtime.continuation import (
    NO_SOURCES_ANSWER_MESSAGE,
    UNVERIFIED_ANSWER_MESSAGE,
)
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.planning.llm_planner import LLMPlanGenerator
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from core.exceptions.rag import EmbeddingError, RerankError, VectorStoreError
from rag.caching_embedding_provider import CachingEmbeddingProvider
from rag.keyword_store import PostgresKeywordStore
from rag.models import Chunk, RetrievalResult
from rag.pgvector_store import PgVectorStore
from rag.reranker import CrossEncoderReranker
from tests.e2e.conftest import STATUTE_EVIDENCE_TEXT

pytestmark = pytest.mark.asyncio

CHAT_MESSAGE = "What does section 2(1)(ta) of the IT Act 2000 define?"

# Echoes the question, so relevance (real local embeddings) passes when
# the embedding model is up.
FINAL_ANSWER = (
    "Section 2(1)(ta) of the IT Act 2000 defines 'electronic signature' "
    "as authentication of an electronic record by a subscriber using an "
    "electronic technique."
)


# Termination reasons of an answer the gate replaced.
UNVERIFIED = {"quality_gate_exhausted", "no_evidence"}


def _statute_result(score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(
            id="it-act-2000-s2-1-ta",
            text=STATUTE_EVIDENCE_TEXT,
            metadata={"title": "Information Technology Act, 2000", "sequence": "1"},
            source="it_act_2000.pdf",
        ),
        score=score,
    )


def _plan() -> ExecutionPlanDTO:
    return ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepDTO(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction=CHAT_MESSAGE,
                depends_on=(),
                stage=1,
                arguments={},
            ),
        ),
        metadata={},
    )


class _Components:
    """Which retrieval components fail, and what each one was asked."""

    def __init__(self) -> None:
        self.down: set[str] = set()
        self.calls: list[str] = []


async def _chat(
    e2e_client: AsyncClient, *, conversation_id: str, headers: dict, components: _Components
):
    async def fake_reason(self, *, request, context=()):
        return AgentDecision(
            decision_type=AgentDecisionType.FINAL,
            reason="Answering.",
            final_response=FINAL_ANSWER,
        )

    async def fake_plan_generate(self, *, request):
        return _plan()

    real_embed = CachingEmbeddingProvider.embed

    async def embed(self, *, texts):
        components.calls.append("embedding")
        if "embedding" in components.down:
            raise EmbeddingError("embedding model not loaded")
        return await real_embed(self, texts=texts)

    async def vector_query(self, **_kwargs):
        components.calls.append("vector")
        if "vector" in components.down:
            raise VectorStoreError("pgvector unavailable")
        return [_statute_result(0.91)]

    async def keyword_query(self, **_kwargs):
        components.calls.append("keyword")
        if "keyword" in components.down:
            raise VectorStoreError("keyword index unavailable")
        return [_statute_result(0.4)]

    async def rerank(self, *, query, candidates, top_k):
        components.calls.append("rerank")
        if "rerank" in components.down:
            raise RerankError("cross-encoder unavailable")
        return [
            RetrievalResult(chunk=candidate.chunk, score=0.9) for candidate in candidates[:top_k]
        ]

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))
        patches.enter_context(patch.object(CachingEmbeddingProvider, "embed", embed))
        patches.enter_context(patch.object(PgVectorStore, "query", vector_query))
        patches.enter_context(patch.object(PostgresKeywordStore, "query", keyword_query))
        patches.enter_context(patch.object(CrossEncoderReranker, "rerank", rerank))

        return await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=headers,
        )


async def test_with_every_component_up_the_answer_is_verified(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hermetic_llm,
) -> None:
    components = _Components()

    response = await _chat(
        e2e_client,
        conversation_id=conversation_id,
        headers=registered_user["headers"],
        components=components,
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["response"]["content"] == FINAL_ANSWER
    assert body["assistant_event"]["event_metadata"].get("termination_reason") not in UNVERIFIED
    assert {"vector", "keyword", "rerank"} <= set(components.calls)


async def test_with_the_reranker_down_the_fused_order_still_answers(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hermetic_llm,
) -> None:
    components = _Components()
    components.down = {"rerank"}

    response = await _chat(
        e2e_client,
        conversation_id=conversation_id,
        headers=registered_user["headers"],
        components=components,
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["response"]["content"] == FINAL_ANSWER
    assert body["assistant_event"]["event_metadata"].get("termination_reason") not in UNVERIFIED
    assert hermetic_llm.groundedness_calls >= 1
    assert "rerank" in components.calls


async def test_with_embeddings_down_keyword_search_runs_and_the_gate_fails_safe(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hermetic_llm,
) -> None:
    components = _Components()
    components.down = {"embedding"}

    response = await _chat(
        e2e_client,
        conversation_id=conversation_id,
        headers=registered_user["headers"],
        components=components,
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    # Keyword-only retrieval found the statute (evidence exists), but the
    # answer couldn't be scored, so it's replaced, not returned unchecked.
    assert "keyword" in components.calls
    assert "vector" not in components.calls
    assert body["response"]["content"] == UNVERIFIED_ANSWER_MESSAGE
    assert FINAL_ANSWER not in body["response"]["content"]
    assert body["assistant_event"]["event_metadata"]["termination_reason"] == (
        "quality_gate_exhausted"
    )


async def test_with_embeddings_and_keyword_search_down_there_are_no_sources(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hermetic_llm,
) -> None:
    components = _Components()
    components.down = {"embedding", "keyword"}

    response = await _chat(
        e2e_client,
        conversation_id=conversation_id,
        headers=registered_user["headers"],
        components=components,
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["response"]["content"] == NO_SOURCES_ANSWER_MESSAGE
    assert body["assistant_event"]["event_metadata"]["termination_reason"] == "no_evidence"
    assert hermetic_llm.groundedness_calls == 0
