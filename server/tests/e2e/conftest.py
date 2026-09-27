"""
Shared fixtures for API-level end-to-end tests.

These tests exercise the real FastAPI app (real Postgres, real Redis,
real Postgres-backed LangGraph checkpointer) over httpx.AsyncClient --
no mock ORM, no fake HTTP layer. The only things ever mocked are the
genuinely external, non-deterministic, or costly boundaries a test
would otherwise have no control over: live LLM "thinking" calls and
an outbound MCP (Gmail/Slack) network call -- never the application's
own routing, persistence, authorization, or HITL logic. See each
test module's own docstring for what it mocks and why. No test reaches a
real LLM provider: the autouse hermetic_llm fixture below stubs the
output guardrail's judge and the answer gate's groundedness judge, and
fails any test that makes another, unmocked LLM call.

Run via `make test-e2e` (needs the real docker compose Postgres/Redis
services up -- `./setup.sh --install --dependency postgres
--dependency redis`), not part of the fast unit-test loop.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.groq import GroqClient  # noqa: F401 -- registers the subclass
from adapters.clients.llm.local import LocalLLMClient  # noqa: F401 -- registers the subclass
from adapters.persistence.sqlalchemy.session import dispose_engine
from agentic.guardrails.harmful_content import RESPONSE_TAG
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO
from main import app as fastapi_app
from rag.hybrid_retriever import HybridRetriever
from rag.models import Chunk, RetrievalResult

# The stubbed harmful-content judge's verdict: "not harmful", so a test's
# (scripted) answer reaches the client exactly as the agent produced it.
_NOT_HARMFUL_VERDICT = '{"harmful": false, "category": null, "reason": "e2e stub"}'


def _llm_client_classes() -> list[type[LLMClient]]:
    """LLMClient and every subclass of it, at any depth."""

    classes: list[type[LLMClient]] = [LLMClient]
    for client_class in classes:
        classes.extend(client_class.__subclasses__())
    return classes


@dataclass
class LLMStub:
    """
    Handle to the hermetic_llm fixture. Set ``judge_error`` BEFORE the
    app starts (i.e. request this fixture ahead of e2e_client) to make
    every harmful-content judge call raise it instead.
    """

    judge_error: Exception | None = None
    judge_calls: int = 0
    # Score the stubbed groundedness judge returns for an answer checked
    # against evidence.
    groundedness: float = 1.0
    groundedness_calls: int = 0
    unexpected_calls: list[str] = field(default_factory=list)


@pytest.fixture(autouse=True)
def hermetic_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[LLMStub]:
    """
    No e2e test reaches a real LLM provider.

    Each test mocks the agent's own LLM calls (planning, reasoning, the
    streamed answer). The one LLM call every chat response still made
    was the output guardrail's harmful-content judge, which went to Groq
    for real: these tests depended on a working provider and API key,
    and when that call failed (bad key, rate limit, outage) the judge
    correctly failed closed and turned every answer into the fixed
    refusal -- a network problem reported as a broken product.

    - The harmful-content judge the guardrail factory builds is replaced
      by a stub returning "not harmful". It replaces the whole cached
      judge callable, not just the provider call beneath it, so no stub
      verdict is ever written to Redis (a shared dev Redis included).
      HarmfulContentJudge's real prompt building, escaping and verdict
      parsing still run on it.
    - The answer gate's groundedness judge (the FaithfulnessBackend the
      executor factory builds) is replaced by a stub returning
      ``LLMStub.groundedness``. It only runs when there is evidence to
      check an answer against (see the statute_evidence fixture).
    - Any other LLMClient.generate() call (generate_structured() goes
      through it too) is recorded and fails the test at teardown, so a
      new unmocked LLM dependency shows up as exactly that instead of as
      a refusal or a flaky network error.
    - Any LLMClient.stream() call is recorded the same way. Nothing
      streams from a model today: /chat/stream sends the reviewed text
      (S2), so a streaming generation reappearing fails every e2e test.
      stream() is patched on every class that defines it -- the Groq and
      local clients override the base method, so patching LLMClient
      alone would miss them.
    """

    stub = LLMStub()

    def stub_build_llm_judge(**_kwargs):
        async def judge(prompt: str) -> str:
            stub.judge_calls += 1
            assert f"<{RESPONSE_TAG}>" in prompt, "not a harmful-content judge prompt"
            if stub.judge_error is not None:
                raise stub.judge_error
            return _NOT_HARMFUL_VERDICT

        return judge

    class StubFaithfulnessBackend:
        async def evaluate(self, *, query: str, answer: str, contexts: list[str]) -> float:
            stub.groundedness_calls += 1
            assert contexts, "groundedness judged without evidence"
            return stub.groundedness

    async def unexpected_generate(self: LLMClient, *, request: LLMRequestDTO) -> LLMResponseDTO:
        prompt = request.messages[-1].content if request.messages else ""
        stub.unexpected_calls.append(prompt[:200])
        return LLMResponseDTO(content="", provider="e2e-stub", model="e2e-stub")

    async def unexpected_stream(self: LLMClient, *, request: LLMRequestDTO):
        prompt = request.messages[-1].content if request.messages else ""
        stub.unexpected_calls.append(f"stream: {prompt[:200]}")
        return
        yield  # an async generator, like the real stream()

    monkeypatch.setattr("wiring.factories.guardrails.build_llm_judge", stub_build_llm_judge)
    monkeypatch.setattr(
        "wiring.factories.executor.build_faithfulness_backend",
        lambda **_kwargs: StubFaithfulnessBackend(),
    )
    monkeypatch.setattr(LLMClient, "generate", unexpected_generate)
    for client_class in _llm_client_classes():
        if "stream" in vars(client_class):
            monkeypatch.setattr(client_class, "stream", unexpected_stream)

    yield stub

    assert not stub.unexpected_calls, (
        "Unmocked LLM call(s) in an e2e test (mock them in the test, like the "
        f"planner/agent calls): {stub.unexpected_calls}"
    )


STATUTE_EVIDENCE_TEXT = (
    "Section 2(1)(ta) of the Information Technology Act, 2000: "
    '"electronic signature" means authentication of any electronic record '
    "by a subscriber by means of the electronic technique specified in the "
    "Second Schedule and includes digital signature."
)


@pytest.fixture
def statute_evidence(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    Give the retriever one statute chunk to find.

    The dev and CI databases hold no ingested corpus, so real retrieval
    finds nothing and every answer that goes through the real answer
    gate becomes the "no sources" answer (evidence is required, A1).
    This patches only HybridRetriever.retrieve -- the Postgres/pgvector
    boundary. RetrieverTool, the agent's evidence seeding, tool policy
    and the answer gate all run for real on the returned chunk.

    Returns the list of queries the retriever received.
    """

    queries: list[str] = []

    async def retrieve(self, *, query: str, top_k: int = 5, **_kwargs):
        queries.append(query)
        return [
            RetrievalResult(
                chunk=Chunk(
                    id="it-act-2000-s2-1-ta",
                    text=STATUTE_EVIDENCE_TEXT,
                    metadata={"title": "Information Technology Act, 2000", "sequence": "1"},
                    source="it_act_2000.pdf",
                ),
                score=0.92,
            ),
        ]

    monkeypatch.setattr(HybridRetriever, "retrieve", retrieve)

    return queries


@pytest.fixture
def empty_corpus(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    Make the retriever find nothing, whatever is in the database.

    For tests that depend on there being no evidence. The dev and CI
    databases are normally empty, but not always: the RAG smoke tests'
    session-scoped fixture keeps its ingested corpus in the database until
    the pytest session ends, so an e2e test run in the same session sees
    it. Like statute_evidence, this patches only HybridRetriever.retrieve
    (the Postgres/pgvector boundary); RetrieverTool, evidence seeding and
    the answer gate run for real.

    Returns the list of queries the retriever received.
    """

    queries: list[str] = []

    async def retrieve(self, *, query: str, top_k: int = 5, **_kwargs):
        queries.append(query)
        return []

    monkeypatch.setattr(HybridRetriever, "retrieve", retrieve)

    return queries


@pytest_asyncio.fixture
async def e2e_client() -> AsyncIterator[AsyncClient]:
    """
    A real httpx client wired directly to the real FastAPI app via
    ASGITransport (no network socket, but every other layer -- routing,
    middleware, dependency injection, exception handlers -- runs
    exactly as it would under uvicorn).

    httpx's ASGITransport does not drive the app's lifespan on its
    own, so it's driven explicitly here via
    app.router.lifespan_context() -- this is what actually runs
    main.py's lifespan(): seeds default agent policies, opens the
    real AsyncPostgresSaver checkpointer, and builds the real
    AIOrchestrator stored on app.state, all against the real
    Postgres/Redis this test run points at.
    """

    # session_factory's shared engine may be holding connections
    # opened under a different event loop from a previous test module
    # (each test function gets its own loop under pytest-asyncio's
    # default function-scoped loop) -- discard them before first use,
    # mirroring tests/smoke/conftest.py's rag_smoke_environment fixture.
    await dispose_engine()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        transport = ASGITransport(app=fastapi_app)

        async with AsyncClient(
            transport=transport,
            base_url="http://e2e.testserver",
        ) as client:
            yield client

    await dispose_engine()


@pytest_asyncio.fixture
async def registered_user(e2e_client: AsyncClient) -> dict:
    """
    Register and log in a fresh user through the real HTTP API --
    the same path any real client takes, not a DB shortcut.

    Returns {"user_id", "email", "headers"} -- "headers" is ready to
    merge into any authenticated request.
    """

    return await _register_and_login(e2e_client)


@pytest_asyncio.fixture
async def second_registered_user(e2e_client: AsyncClient) -> dict:
    """
    A second, independent user, for cross-user authorization tests.
    Same shape as ``registered_user``.
    """

    return await _register_and_login(e2e_client)


async def _register_and_login(e2e_client: AsyncClient) -> dict:
    email = f"e2e-{uuid.uuid4().hex[:16]}@example.com"
    password = "Str0ng-E2E-Passw0rd!"

    register_response = await e2e_client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "first_name": "E2E",
            "last_name": "Tester",
        },
    )
    assert register_response.status_code == 201, register_response.text
    user_id = register_response.json()["data"]["id"]

    login_response = await e2e_client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    login_body = login_response.json()
    # /auth/login returns LoginResponse's fields directly (response_model=None,
    # and the endpoint returns the pydantic model bare rather than wrapped
    # in ApiResponse) -- not the {"data": {...}} envelope most other
    # endpoints use. Handle both shapes defensively rather than assume
    # one silently breaks the other if it's ever made consistent.
    access_token = (
        login_body["data"]["access_token"]
        if "data" in login_body and login_body["data"]
        else login_body["access_token"]
    )

    return {
        "user_id": user_id,
        "email": email,
        "headers": {"Authorization": f"Bearer {access_token}"},
    }


@pytest_asyncio.fixture
async def conversation_id(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> str:
    """
    Create a real conversation for registered_user, via the real HTTP
    API.
    """

    response = await e2e_client.post(
        "/api/v1/conversations",
        json={},
        headers=registered_user["headers"],
    )
    assert response.status_code == 201, response.text

    return response.json()["data"]["id"]
