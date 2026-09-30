"""
Benchmark the planner's LLM call on Groq vs local Ollama (review R18).

Runs the real LLM planner (LLMPlanGenerator: the real planning prompt, the
agent-capability block read from the agent_policies table, the real
structured-output schema) against each provider on the same sample
questions, validates every plan with the real ExecutionPlanValidator, and
reports per provider: success rate, latency (p50/p95/max), token usage and
the errors seen. Nothing is executed and nothing is written.

It exists to inform the R18 decision (keep the planner on local Ollama,
move it to Groq, or fail over between them); it doesn't change the wiring.

Usage (from server/, services on the host):

    DB_HOST=localhost REDIS_HOST=localhost \\
    LLM_LOCAL_BASE_URL=http://localhost:11434 \\
    PYTHONPATH=src poetry run python scripts/bench_planner.py \\
        [--providers groq local] [--start 0] [--count 20] \\
        [--timeout 180] [--out bench_planner.jsonl] [--report]

Each run appends one JSON line per call to --out, so a long local run can
be split into slices (--start/--count); --report summarizes the file.

Makes real provider calls: Groq calls count against the API key's quota
(about 2-3k tokens per plan).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from adapters.persistence.sqlalchemy.session import session_factory
from agentic.planning.capabilities import AgentCapabilityCatalog
from agentic.planning.llm_planner import LLMPlanGenerator
from agentic.planning.prompts.planning import PlanningPromptBuilder
from agentic.planning.validator import ExecutionPlanValidator
from agentic.policy.agent_policy import DatabaseAgentPolicyProvider
from application.authorization.approval_lifecycle.verifier import ApprovalRecordVerifier
from config.settings import get_settings
from core.dto.planning import PlanningRequestDTO
from core.enums import LLMProviderEnum
from core.usage import usage_scope
from wiring.factories.agents import register_agents
from wiring.factories.clients import create_clients
from wiring.factories.llm_resolver import build_llm_resolver
from wiring.factories.registries import create_registries
from wiring.factories.tools import register_tools

# Mixed on purpose: statute look-ups, multi-part questions, contract work,
# and requests no agent can serve (the planner should decline, not invent).
QUESTIONS = [
    "What does Section 66A of the IT Act 2000 say?",
    "Explain the punishment for identity theft under the IT Act.",
    "Is Article 21 of the Constitution applicable to private companies?",
    "What reservations does the Reservation Act 1985 provide for?",
    "Compare Article 14 and Article 15 of the Constitution.",
    "Summarise the fundamental rights in Part III of the Constitution.",
    "Which section of the IT Act covers cyber terrorism, and what is the penalty?",
    "Review this clause: 'The vendor shall not be liable for any indirect loss.'",
    "What should a non-disclosure agreement between two startups include?",
    "Compare a limitation of liability clause with an indemnity clause.",
    "Is an electronic signature valid for a rental agreement in India?",
    "What remedies does a company have if its database is hacked?",
    "Explain Section 43 of the IT Act and how compensation is assessed.",
    "Can a state government make reservations in promotions?",
    "What are the duties of an intermediary under the IT Act?",
    "Draft the key points for a termination clause in an employment contract.",
    "Check my email for updates on case 84021.",
    "Book a meeting with opposing counsel next Tuesday.",
    "What is the weather in Delhi today?",
    "Hi, what can you help me with?",
]


def _registries() -> Any:
    """Agents and tools registered as in create_ai_orchestrator(), for the capability block."""

    settings = get_settings()
    clients = create_clients(settings=settings)
    registries = create_registries()
    register_tools(
        clients=clients,
        registries=registries,
        approval_service=ApprovalRecordVerifier(session_factory=session_factory),
    )
    register_agents(settings=settings, clients=clients, registries=registries)
    return registries


def _planner(llm_client: Any, registries: Any, *, timeout: float) -> LLMPlanGenerator:
    settings = get_settings()

    return LLMPlanGenerator(
        llm_client=llm_client,
        prompt_builder=PlanningPromptBuilder(max_steps=settings.agent_policy.PLAN_MAX_STEPS),
        capability_catalog=AgentCapabilityCatalog(
            agent_registry=registries.agent_registry,
            tool_registry=registries.tool_registry,
            agent_policy_provider=DatabaseAgentPolicyProvider(session_factory=session_factory),
        ),
        timeout_seconds=timeout,
    )


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    resolver = build_llm_resolver(settings=settings)
    validator = ExecutionPlanValidator(max_steps=settings.agent_policy.PLAN_MAX_STEPS)
    questions = QUESTIONS[args.start : args.start + args.count]
    out = Path(args.out)
    registries = _registries()

    for provider_name in args.providers:
        provider = LLMProviderEnum(provider_name)
        client = resolver.get(provider)
        planner = _planner(client, registries, timeout=args.timeout)

        for offset, question in enumerate(questions):
            index = args.start + offset
            record: dict[str, Any] = {
                "provider": provider.value,
                "model": client.model,
                "index": index,
                "question": question,
            }
            started = time.monotonic()

            try:
                with usage_scope() as meter:
                    plan = await planner.generate(
                        request=PlanningRequestDTO(message=question, history=(), user_memory=()),
                    )
                validator.validate(plan)
                record.update(ok=True, steps=len(plan.steps), intent=str(plan.intent))
            except Exception as exc:
                record.update(ok=False, error=type(exc).__name__, detail=str(exc)[:200])
            finally:
                record["seconds"] = round(time.monotonic() - started, 2)

            record["tokens"] = meter.total_tokens
            print(json.dumps(record), flush=True)

            with out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")


def _report(path: Path) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    by_provider: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        by_provider.setdefault(f"{row['provider']} ({row['model']})", []).append(row)

    print("| Provider | Calls | Valid plans | p50 s | p95 s | max s | mean tokens | Errors |")
    print("|---|---|---|---|---|---|---|---|")

    for name, results in by_provider.items():
        seconds = sorted(row["seconds"] for row in results)
        ok = sum(1 for row in results if row["ok"])
        p95 = seconds[min(len(seconds) - 1, round(0.95 * (len(seconds) - 1)))]
        errors: dict[str, int] = {}
        for row in results:
            if not row["ok"]:
                errors[row["error"]] = errors.get(row["error"], 0) + 1
        tokens = [row["tokens"] for row in results if row["tokens"]]

        print(
            f"| {name} | {len(results)} | {ok}/{len(results)} ({100 * ok / len(results):.0f}%) "
            f"| {statistics.median(seconds):.1f} | {p95:.1f} | {seconds[-1]:.1f} "
            f"| {statistics.mean(tokens) if tokens else 0:.0f} "
            f"| {', '.join(f'{k} x{v}' for k, v in errors.items()) or '-'} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--providers", nargs="+", default=["groq", "local"])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=len(QUESTIONS))
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--out", default="bench_planner.jsonl")
    parser.add_argument("--report", action="store_true", help="Summarize --out and exit.")
    args = parser.parse_args()

    if args.report:
        _report(Path(args.out))
        return

    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
