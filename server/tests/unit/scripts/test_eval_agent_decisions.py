"""
Unit tests: scripts/python/eval_agent_decisions.py (review M1).

The A/B of the agent decision schema on Groq: arm A sends AgentDecision's
own schema, arm B the narrower enum schema (GROQ_SEND_RESPONSE_SCHEMA).
The live run is decided for once on the dev key after quota tuning, capped
at 2 repeats per question and a hard stop at 500k tokens, aborting on a
rate-limit error. Everything but the live turn is tested here, with a fake
turn runner: the plan, the token budget, the aborts, the summary and the
verdicts the review's thresholds give for A20, A19 and A17 part 2.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

SERVER = Path(__file__).resolve().parents[3]
SCRIPT = SERVER / "scripts" / "python" / "eval_agent_decisions.py"
DATASET = SERVER / "tests" / "datasets" / "rag" / "evaluation" / "legal_retrieval_gold_v2.json"


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eval_agent_decisions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _turn(script: ModuleType, **overrides):
    values = {
        "question_id": "it-001",
        "kind": "golden",
        "repeat": 1,
        "status_code": 200,
        "termination": "completed",
        "answer_verified": True,
        "golden_hit": True,
        "decisions": Counter({"tool_call": 1, "final": 1}),
        "rejections": Counter(),
        "tool_calls": 1,
        "llm_calls": 2,
        "agent_executions": 1,
        "tokens": 1_000,
        "latency_s": 4.0,
        "rate_limited": False,
        "fallback": False,
    }
    values.update(overrides)
    return script.Turn(**values)


# --- the plan ---------------------------------------------------------------


def test_the_plan_runs_every_golden_question_for_each_repeat(script: ModuleType) -> None:
    plan = script.build_plan(dataset=DATASET, repeats=2, include_extra=False)

    assert len(plan) == 60 * 2
    assert {question.kind for question, _repeat in plan} == {"golden"}
    assert [repeat for _question, repeat in plan[:2]] == [1, 1]


def test_extra_questions_are_opt_in(script: ModuleType) -> None:
    plan = script.build_plan(dataset=DATASET, repeats=1, include_extra=True)

    kinds = Counter(question.kind for question, _repeat in plan)
    assert kinds["golden"] == 60
    assert kinds["no_evidence"] >= 15
    assert kinds["unlisted_tool"] >= 8


def test_the_arms_set_the_groq_schema_switch(script: ModuleType) -> None:
    assert script.ARMS == {"A": "false", "B": "true"}
    assert script.parse_args(["--arm", "B"]).arm == "B"
    with pytest.raises(SystemExit):
        script.parse_args(["--arm", "C"])


def test_the_decided_caps_are_the_defaults(script: ModuleType) -> None:
    args = script.parse_args(["--arm", "A"])

    assert args.repeats == 2
    assert args.max_tokens == 500_000
    assert args.include_extra is False


# --- the budget and the aborts ----------------------------------------------


def test_the_budget_stops_before_a_turn_that_could_cross_the_cap(script: ModuleType) -> None:
    budget = script.TokenBudget(cap=10_000)

    assert budget.allows_next_turn()
    budget.add(4_000)
    assert budget.allows_next_turn()
    budget.add(4_000)
    # 8,000 used; the largest turn so far was 4,000, so the next could cross.
    assert not budget.allows_next_turn()
    assert budget.used == 8_000


async def test_a_run_stops_at_the_token_budget(script: ModuleType) -> None:
    plan = script.build_plan(dataset=DATASET, repeats=1, include_extra=False)
    calls = 0

    async def run_turn(question, repeat):
        nonlocal calls
        calls += 1
        return _turn(script, question_id=question.id, tokens=3_000)

    turns, stopped = await script.run_arm(
        plan=plan, run_turn=run_turn, budget=script.TokenBudget(cap=10_000)
    )

    assert stopped == "token_budget"
    assert calls == len(turns) == 3
    assert sum(turn.tokens for turn in turns) <= 10_000


async def test_a_run_aborts_on_a_rate_limit(script: ModuleType) -> None:
    plan = script.build_plan(dataset=DATASET, repeats=1, include_extra=False)

    async def run_turn(question, repeat):
        return _turn(script, question_id=question.id, rate_limited=question.id == "it-003")

    turns, stopped = await script.run_arm(
        plan=plan, run_turn=run_turn, budget=script.TokenBudget(cap=500_000)
    )

    assert stopped == "rate_limited"
    assert [turn.question_id for turn in turns] == ["it-001", "it-002", "it-003"]


async def test_a_complete_run_says_so(script: ModuleType) -> None:
    plan = script.build_plan(dataset=DATASET, repeats=1, include_extra=False)[:4]

    async def run_turn(question, repeat):
        return _turn(script, question_id=question.id)

    turns, stopped = await script.run_arm(
        plan=plan, run_turn=run_turn, budget=script.TokenBudget(cap=500_000)
    )

    assert stopped == "completed"
    assert len(turns) == 4


# --- the summary -------------------------------------------------------------


def test_the_summary_reports_rates_counts_and_latency(script: ModuleType) -> None:
    turns = [
        _turn(script, latency_s=2.0),
        _turn(
            script,
            question_id="it-002",
            golden_hit=False,
            answer_verified=False,
            termination="failed_policy",
            decisions=Counter({"tool_call": 3, "final": 1}),
            rejections=Counter({"policy_denied_unlisted": 1, "planner_argument": 1}),
            llm_calls=4,
            latency_s=10.0,
        ),
    ]

    summary = script.summarize(turns, stopped="completed")

    assert summary["turns"] == 2
    assert summary["tokens_used"] == 2_000
    assert summary["decisions"] == 6
    assert summary["rejection_rate_by_cause"]["policy_denied_unlisted"] == pytest.approx(1 / 6)
    assert summary["golden_pass_rate"] == 0.5
    assert summary["unverified_rate"] == 0.5
    assert summary["failed_turn_rate"] == 0.5
    assert summary["llm_calls_per_turn"] == 3.0
    assert summary["latency_s"] == {"p50": 2.0, "p95": 10.0}
    assert summary["stopped"] == "completed"


def test_the_summary_holds_no_question_or_answer_text(script: ModuleType) -> None:
    summary = script.summarize([_turn(script)], stopped="completed")

    text = json.dumps(summary)
    assert "territorial" not in text


# --- the verdicts (review M1 thresholds) ------------------------------------


def _summary(script, **overrides) -> dict:
    base = {
        "turns": 100,
        "decisions": 200,
        "agent_executions": 100,
        "golden_pass_rate": 0.80,
        "unverified_rate": 0.10,
        "failed_turn_rate": 0.01,
        "llm_calls_per_turn": 2.0,
        "rejections": {},
    }
    base.update(overrides)
    return base


def test_a20_adopts_the_enum_when_it_cuts_unlisted_tools_without_costing_quality(
    script: ModuleType,
) -> None:
    a = _summary(script, rejections={"policy_denied_unlisted": 10})
    b = _summary(script, rejections={"policy_denied_unlisted": 4}, llm_calls_per_turn=2.1)

    assert script.verdicts(a, b)["A20"].startswith("adopt")


def test_a20_closes_when_the_enum_costs_quality(script: ModuleType) -> None:
    a = _summary(script, rejections={"policy_denied_unlisted": 10})
    b = _summary(script, rejections={"policy_denied_unlisted": 2}, golden_pass_rate=0.75)

    assert script.verdicts(a, b)["A20"].startswith("close")


def test_a19_builds_strict_only_past_the_rejection_threshold(script: ModuleType) -> None:
    low = _summary(script, rejections={"invalid_decision": 1, "parse_failure": 1})
    high = _summary(script, rejections={"invalid_decision": 3, "tool_params_rejected": 2})

    assert script.verdicts(low, low)["A19"].startswith("close")
    assert script.verdicts(high, high)["A19"].startswith("build arm C")


def test_a17_part_2_defines_step_arguments_past_the_planner_threshold(script: ModuleType) -> None:
    quiet = _summary(script, rejections={"planner_argument": 0, "invalid_decision": 4})
    noisy = _summary(script, rejections={"planner_argument": 2, "invalid_decision": 4})

    assert script.verdicts(quiet, quiet)["A17-2"].startswith("close")
    assert script.verdicts(noisy, noisy)["A17-2"].startswith("define step arguments")
