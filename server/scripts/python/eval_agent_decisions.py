"""
A/B of the agent decision schema on Groq (review M1).

    PYTHONPATH=src poetry run python scripts/python/eval_agent_decisions.py \
        --arm A|B [--repeats 2] [--max-tokens 500000] [--include-extra] \
        [--dataset PATH] [--output FILE] [--dry-run]
    PYTHONPATH=src poetry run python scripts/python/eval_agent_decisions.py \
        --compare A.json B.json

Arm A sends Groq AgentDecision's own schema (today); arm B the narrower
schema whose tool name is an enum of the agent's tools
(GROQ_SEND_RESPONSE_SCHEMA=true, what Ollama already gets). Arm C (Groq
`strict`) is built only if arm A passes the A19 threshold.

Each turn is a real chat request through the in-process app (the full
agent path, real policies, tools and Groq; a fresh conversation per turn),
against the database the settings point at, which must hold the ingested
golden corpus. The decided limits (2026-10-01): run once on the dev key
after quota tuning, 2 repeats, a hard stop before the total Groq tokens
could pass --max-tokens, and an abort on the first rate-limit error. The
actual token use is recorded.

The output holds counts, rates and latencies only, never question or answer
text. --compare prints what the review's thresholds give for A20 (adopt the
enum on Groq), A19 (build arm C) and A17 part 2 (define plan-step arguments).

Exit codes: 0 ok (including a stop at the budget), 1 aborted on a rate
limit or failed to start.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATASET_PATH = Path("tests/datasets/rag/evaluation/legal_retrieval_gold_v2.json")

# GROQ_SEND_RESPONSE_SCHEMA per arm.
ARMS = {"A": "false", "B": "true"}

UNVERIFIED_TERMINATIONS = frozenset({"quality_gate_exhausted", "no_evidence"})
FAILED_TERMINATIONS = frozenset({"failed_validation", "failed_policy"})

# Questions the corpus can't answer: retrieval should find nothing, and the
# agent should say so (or answer from general knowledge where policy allows).
NO_EVIDENCE_QUESTIONS = (
    "What is the punishment for murder under the Indian Penal Code?",
    "How do I register a trademark in India?",
    "What is the limitation period for filing a civil suit for recovery of money?",
    "Can a tenant be evicted without notice under rent control laws?",
    "What are the grounds for divorce under the Hindu Marriage Act?",
    "How is income tax calculated for salaried employees?",
    "What does the Consumer Protection Act say about defective goods?",
    "What is the minimum wage in Maharashtra?",
    "How do I file a first information report for a stolen car?",
    "What are the rules for adopting a child in India?",
    "What is the stamp duty on a property sale in Delhi?",
    "Can an employer deduct salary for late attendance?",
    "What is the procedure for anticipatory bail?",
    "How long does a patent last in India?",
    "What are the rights of an arrested person under the Constitution?",
    "Is a verbal agreement legally binding in India?",
    "What is the penalty for drunk driving in India?",
    "How is a will probated in India?",
    "What does the Right to Information Act require of public authorities?",
    "What is the process to change my name legally?",
)

# Prompts that press for a tool no agent may use (as in the R2 smoke test).
UNLISTED_TOOL_PROMPTS = (
    "Email the summary of section 43 of the IT Act to my lawyer.",
    "Post a message in our Slack channel about the Handlooms Act penalties.",
    "Check my inbox for updates on my cyber fraud complaint.",
    "Search the web for the latest Supreme Court ruling on section 66A.",
    "Run a database query to list all my past cases.",
    "Book an appointment with a cyber law expert for tomorrow.",
    "Download the latest amendment to the IT Act and attach it here.",
    "Send an SMS to my client with the bail conditions.",
    "Open the court's e-filing portal and file my petition.",
    "Translate the IT Act section 79 into Hindi using a translation tool.",
)


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    query: str
    kind: str  # golden | no_evidence | unlisted_tool
    expected_evidence: tuple[str, ...] = ()


@dataclass(slots=True)
class Turn:
    question_id: str
    kind: str
    repeat: int
    status_code: int
    termination: str
    answer_verified: bool | None
    golden_hit: bool | None
    decisions: Counter[str] = field(default_factory=Counter)
    rejections: Counter[str] = field(default_factory=Counter)
    tool_calls: int = 0
    llm_calls: int = 0
    agent_executions: int = 0
    tokens: int = 0
    latency_s: float = 0.0
    rate_limited: bool = False
    fallback: bool = False


class TokenBudget:
    """
    A hard stop on the run's Groq tokens: the next turn starts only if,
    at the size of the largest turn so far, it can't cross the cap.
    """

    def __init__(self, *, cap: int) -> None:
        self.cap = cap
        self.used = 0
        self._largest_turn = 0

    def allows_next_turn(self) -> bool:
        return self.used + self._largest_turn <= self.cap and self.used < self.cap

    def add(self, tokens: int) -> None:
        self.used += tokens
        self._largest_turn = max(self._largest_turn, tokens)


def build_plan(*, dataset: Path, repeats: int, include_extra: bool) -> list[tuple[Question, int]]:
    """
    `repeats` passes over every question (golden ones first), so a run
    stopped at the token budget still covers the whole set once.
    """

    cases = json.loads(dataset.read_text(encoding="utf-8"))["cases"]
    questions = [
        Question(
            id=case["id"],
            query=case["query"],
            kind="golden",
            expected_evidence=tuple(case["expected_evidence"]),
        )
        for case in cases
    ]

    if include_extra:
        questions += [
            Question(id=f"ne-{index:03d}", query=query, kind="no_evidence")
            for index, query in enumerate(NO_EVIDENCE_QUESTIONS, start=1)
        ]
        questions += [
            Question(id=f"ut-{index:03d}", query=query, kind="unlisted_tool")
            for index, query in enumerate(UNLISTED_TOOL_PROMPTS, start=1)
        ]

    return [(question, repeat) for repeat in range(1, repeats + 1) for question in questions]


RunTurn = Callable[[Question, int], Awaitable[Turn]]


async def run_arm(
    *,
    plan: Sequence[tuple[Question, int]],
    run_turn: RunTurn,
    budget: TokenBudget,
) -> tuple[list[Turn], str]:
    """Run the plan until it ends, the budget stops it, or a rate limit hits."""

    turns: list[Turn] = []

    for question, repeat in plan:
        if not budget.allows_next_turn():
            return turns, "token_budget"

        turn = await run_turn(question, repeat)
        turns.append(turn)
        budget.add(turn.tokens)

        if turn.rate_limited:
            return turns, "rate_limited"

    return turns, "completed"


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(1, math.ceil(percentile / 100 * len(ordered))) - 1]


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(turns: Sequence[Turn], *, stopped: str) -> dict[str, Any]:
    """Counts, rates and latencies for one arm: no question or answer text."""

    decisions: Counter[str] = Counter()
    rejections: Counter[str] = Counter()
    for turn in turns:
        decisions.update(turn.decisions)
        rejections.update(turn.rejections)

    decision_count = sum(decisions.values())
    golden = [turn for turn in turns if turn.kind == "golden" and turn.golden_hit is not None]
    verified = [turn for turn in turns if turn.answer_verified is not None]
    no_evidence = [turn for turn in turns if turn.kind == "no_evidence"]

    return {
        "stopped": stopped,
        "turns": len(turns),
        "tokens_used": sum(turn.tokens for turn in turns),
        "decisions": decision_count,
        "decisions_by_type": dict(decisions),
        "agent_executions": sum(turn.agent_executions for turn in turns),
        "rejections": dict(rejections),
        "rejection_rate_by_cause": {
            cause: count / decision_count for cause, count in rejections.items() if decision_count
        },
        "golden_pass_rate": _rate(sum(1 for turn in golden if turn.golden_hit), len(golden)),
        "unverified_rate": _rate(
            sum(1 for turn in verified if not turn.answer_verified), len(verified)
        ),
        "failed_turn_rate": _rate(
            sum(1 for turn in turns if turn.termination in FAILED_TERMINATIONS or turn.fallback),
            len(turns),
        ),
        "tool_calls_per_turn": _rate(sum(turn.tool_calls for turn in turns), len(turns)),
        "llm_calls_per_turn": _rate(sum(turn.llm_calls for turn in turns), len(turns)),
        "tokens_per_turn": _rate(sum(turn.tokens for turn in turns), len(turns)),
        "latency_s": {
            "p50": _percentile([turn.latency_s for turn in turns], 50),
            "p95": _percentile([turn.latency_s for turn in turns], 95),
        },
        "no_evidence": {
            "turns": len(no_evidence),
            "answered_without_retrieval": sum(1 for turn in no_evidence if turn.tool_calls == 0),
            "no_sources_answer": sum(
                1 for turn in no_evidence if turn.termination == "no_evidence"
            ),
        },
    }


def verdicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, str]:
    """
    What the review's M1 thresholds give for A20, A19 and A17 part 2.

    A20: adopt B if, versus A, the golden pass rate is within 1 point, the
    unverified rate is not higher, LLM calls per turn rise at most 10%, and
    unlisted-tool rejections fall by at least half.
    A19: build arm C if, in arm A, invalid + parse + unlisted + parameter
    rejections are at least 2% of decisions, or at least 5% of turns fail.
    A17 part 2: define step arguments if planner-attributed rejections are
    at least 1% of agent executions or 10% of all rejections (arm A).
    """

    def rejections(summary: dict[str, Any], cause: str) -> int:
        return int(summary["rejections"].get(cause, 0))

    a_unlisted = rejections(a, "policy_denied_unlisted")
    b_unlisted = rejections(b, "policy_denied_unlisted")
    a20_ok = (
        (b["golden_pass_rate"] or 0) >= (a["golden_pass_rate"] or 0) - 0.01
        and (b["unverified_rate"] or 0) <= (a["unverified_rate"] or 0)
        and (b["llm_calls_per_turn"] or 0) <= 1.10 * (a["llm_calls_per_turn"] or 0)
        and a_unlisted > 0
        and b_unlisted <= 0.5 * a_unlisted
    )

    model_errors = sum(
        rejections(a, cause)
        for cause in (
            "invalid_decision",
            "parse_failure",
            "policy_denied_unlisted",
            "tool_params_rejected",
        )
    )
    a19_build = (a["decisions"] and model_errors / a["decisions"] >= 0.02) or (
        a["failed_turn_rate"] or 0
    ) >= 0.05

    planner = rejections(a, "planner_argument")
    all_rejections = sum(
        count for cause, count in a["rejections"].items() if cause != "planner_argument"
    )
    a17_define = (a["agent_executions"] and planner / a["agent_executions"] >= 0.01) or (
        all_rejections and planner / all_rejections >= 0.10
    )

    return {
        "A20": (
            "adopt the enum schema on Groq (GROQ_SEND_RESPONSE_SCHEMA=true)"
            if a20_ok
            else "close: measured, not adopted; Groq keeps the plain schema"
        ),
        "A19": (
            "build arm C (Groq strict) and measure it"
            if a19_build
            else "close: post-generation checks are enough"
        ),
        "A17-2": (
            "define step arguments as task inputs in planning.md, then re-measure"
            if a17_define
            else "close: tool names and purposes only"
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A/B of the agent decision schema on Groq.")
    parser.add_argument("--arm", choices=sorted(ARMS), help="A: plain schema, B: enum schema.")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=500_000)
    parser.add_argument("--include-extra", action="store_true", default=False)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("A_JSON", "B_JSON"))
    args = parser.parse_args(argv)

    if args.compare is None and args.arm is None:
        parser.error("--arm is required unless --compare is given")
    return args


async def _live_runner(
    arm: str,
) -> tuple[RunTurn, Callable[[], Awaitable[None]]]:  # pragma: no cover
    """
    The in-process app, set up for one arm, and a turn runner over HTTP.

    Not unit-tested: it needs the live Groq key and an ingested corpus.
    """

    os.environ["GROQ_SEND_RESPONSE_SCHEMA"] = ARMS[arm]
    # The script's own app instance: its per-minute request limit would
    # otherwise pace the run.
    os.environ.setdefault("RATE_LIMIT_REQUESTS_PER_MINUTE", "100000")

    from httpx import ASGITransport, AsyncClient

    from adapters.clients.llm.groq import GroqClient
    from adapters.observability.metrics import metrics
    from adapters.persistence.sqlalchemy.session import dispose_engine
    from core.exceptions.client import ClientRateLimitError
    from main import app
    from rag.evaluation.metrics.text_matching import evidence_in_text
    from rag.hybrid_retriever import HybridRetriever

    current: dict[str, Any] = {}

    def reset() -> None:
        current.update(
            decisions=Counter(),
            rejections=Counter(),
            tool_calls=0,
            llm_calls=0,
            executions=0,
            tokens=0,
            rate_limited=False,
            fallback=False,
            retrieved=[],
        )

    def on_decision(*, agent: str, decision_type: str) -> None:
        current["decisions"][decision_type] += 1

    def on_rejection(*, agent: str, cause: str) -> None:
        current["rejections"][cause] += 1

    def on_execution(*, agent: str, termination: str, tool_calls: int, llm_calls: int) -> None:
        current["executions"] += 1
        current["tool_calls"] += tool_calls
        current["llm_calls"] += llm_calls

    real_record_llm_call = metrics.record_llm_call

    def on_llm_call(*, provider: str, model: str, duration: float, usage: Any) -> None:
        if provider == "groq" and usage is not None:
            current["tokens"] += usage.total_tokens
        real_record_llm_call(provider=provider, model=model, duration=duration, usage=usage)

    def on_fallback(*, reason: str) -> None:
        current["fallback"] = True

    metrics.record_agent_decision = on_decision  # type: ignore[method-assign]
    metrics.record_rejected_decision = on_rejection  # type: ignore[method-assign]
    metrics.record_agent_execution = on_execution  # type: ignore[method-assign]
    metrics.record_llm_call = on_llm_call  # type: ignore[method-assign]
    metrics.record_orchestration_fallback = on_fallback  # type: ignore[method-assign]

    real_generate = GroqClient._generate

    async def watched_generate(self: GroqClient, *, request: Any) -> Any:
        try:
            return await real_generate(self, request=request)
        except ClientRateLimitError:
            current["rate_limited"] = True
            raise

    GroqClient._generate = watched_generate  # type: ignore[method-assign]

    real_retrieve = HybridRetriever.retrieve

    async def watched_retrieve(self: HybridRetriever, **kwargs: Any) -> Any:
        results = await real_retrieve(self, **kwargs)
        current["retrieved"].extend(result.chunk.text for result in results)
        return results

    HybridRetriever.retrieve = watched_retrieve  # type: ignore[method-assign]

    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://eval.local")

    email = f"m1-eval-{uuid.uuid4().hex[:12]}@example.com"
    password = f"M1-{uuid.uuid4().hex}!a"
    created = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "first_name": "M1",
            "last_name": "Eval",
        },
    )
    created.raise_for_status()
    login = (
        await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    ).json()
    token = (login.get("data") or login)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async def run_turn(question: Question, repeat: int) -> Turn:
        reset()
        conversation = await client.post("/api/v1/conversations", json={}, headers=headers)
        conversation.raise_for_status()

        started = time.perf_counter()
        response = await client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation.json()["data"]["id"], "message": question.query},
            headers=headers,
        )
        latency = time.perf_counter() - started

        metadata: dict[str, Any] = {}
        if response.status_code == 200:
            metadata = response.json()["data"]["assistant_event"].get("event_metadata") or {}
        termination = metadata.get("termination_reason") or (
            "completed" if response.status_code == 200 else f"http_{response.status_code}"
        )

        golden_hit = None
        if question.kind == "golden":
            golden_hit = any(
                evidence_in_text(evidence, text)
                for evidence in question.expected_evidence
                for text in current["retrieved"]
            )

        return Turn(
            question_id=question.id,
            kind=question.kind,
            repeat=repeat,
            status_code=response.status_code,
            termination=termination,
            answer_verified=(
                termination not in UNVERIFIED_TERMINATIONS if response.status_code == 200 else None
            ),
            golden_hit=golden_hit,
            decisions=current["decisions"],
            rejections=current["rejections"],
            tool_calls=current["tool_calls"],
            llm_calls=current["llm_calls"],
            agent_executions=current["executions"],
            tokens=current["tokens"],
            latency_s=latency,
            rate_limited=current["rate_limited"],
            fallback=current["fallback"],
        )

    async def close() -> None:
        await client.aclose()
        await lifespan.__aexit__(None, None, None)
        await dispose_engine()

    return run_turn, close


async def main(args: argparse.Namespace) -> int:
    if args.compare is not None:
        a, b = (json.loads(path.read_text(encoding="utf-8"))["summary"] for path in args.compare)
        for item, verdict in verdicts(a, b).items():
            print(f"{item}: {verdict}")
        return 0

    plan = build_plan(dataset=args.dataset, repeats=args.repeats, include_extra=args.include_extra)
    print(
        f"Arm {args.arm}: {len(plan)} turns planned "
        f"({len(plan) // args.repeats} questions x {args.repeats}); "
        f"hard stop before {args.max_tokens:,} Groq tokens."
    )
    if args.dry_run:
        return 0

    try:
        run_turn, close = await _live_runner(args.arm)
    except Exception as exc:  # pragma: no cover - live setup
        print(f"ERROR: could not start the app: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    budget = TokenBudget(cap=args.max_tokens)
    try:
        turns, stopped = await run_arm(plan=plan, run_turn=run_turn, budget=budget)
    finally:
        await close()

    summary = summarize(turns, stopped=stopped)
    print(json.dumps(summary, indent=2))

    if args.output is not None:
        args.output.write_text(
            json.dumps(
                {
                    "arm": args.arm,
                    "groq_send_response_schema": ARMS[args.arm],
                    "dataset": str(args.dataset),
                    "repeats": args.repeats,
                    "max_tokens": args.max_tokens,
                    "summary": summary,
                    "turns": [
                        {
                            "question_id": turn.question_id,
                            "kind": turn.kind,
                            "repeat": turn.repeat,
                            "status_code": turn.status_code,
                            "termination": turn.termination,
                            "golden_hit": turn.golden_hit,
                            "decisions": dict(turn.decisions),
                            "rejections": dict(turn.rejections),
                            "tool_calls": turn.tool_calls,
                            "llm_calls": turn.llm_calls,
                            "tokens": turn.tokens,
                            "latency_s": round(turn.latency_s, 3),
                        }
                        for turn in turns
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return 1 if stopped == "rate_limited" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
