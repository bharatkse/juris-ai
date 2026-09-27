---
name: agent-execution-governance
description: Agent turn budgets, prompt pruning, _gate_final, loop breaker, HITL idempotency, and prompt-injection boundaries. Use when changing agent runtime, evaluation gate, token quotas, or tool replay.
---

# Agent execution governance

## Budgets (what exists)

`AgentExecutionBudget` (`agents/runtime/lifecycle/budget.py`): iterations, tool calls, hops, steps, wall time, repeated-action / no-progress / rejected-decision caps, collection and char limits. **No `max_cost_usd` field** — do not add one unless product asks. Token spend is `core/usage.py` `UsageMeter` + `TOKEN_QUOTA_DAILY` / `TOKEN_QUOTA_PER_REQUEST` (413 `REQUEST_TOKEN_QUOTA_EXCEEDED`). Prompt size: `fit_to_budget()` / `context_window_for()` in `agents/prompts/token_budget.py` (tiktoken cl100k_base + margin; keep system prompt; trim history then low-score context).

Graph timeout: `ExecutionTimeoutPolicy` (~300s) + `core.deadline`. Planner has `PLANNER_TIMEOUT_S` and Groq failover.

## Evaluator gate

`AgentContinuationService._gate_final()`: groundedness/relevance via `AnswerEvaluator`. Insufficient groundedness/relevance → `_force_corrective_retrieval` (still `check_tool("retriever")`). Judge or embeddings down → do not accept unscored answers (skip retry). Caller must **return** a rejected FINAL, never re-gate (infinite loop). `enforce_citations` stays off (K14).

## Circuit breaker analog

There is no named circuit breaker. Use `LoopBreaker` + `BudgetGuard` (`max_repeated_action`, `max_no_progress`). LLM provider errors are Groq SDK retries then optional `FailoverLLMClient`, not this loop.

## Idempotency

- Gated send: verifier + `claim()` + decision row `waiting` → 409.
- Tool replay: `@task` around `_execute_tool()`.
- Usage: `UsageService.record()` idempotent on request id.
- Policy seed: agent_policies upsert every startup; **roles** are create-if-missing.

## Prompt-injection boundary

Untrusted retrieval/web/upload text: `escape_delimiter()` (`core/utils/prompt_safety.py`), `SecuritySanitizer` on tool output. Evidence belongs in `build_context()` (`<retrieved_context>`), not spliced into the system prompt. Known gap **S6**: retrieved chunks are still `SYSTEM` role; do not add more untrusted SYSTEM text. Parameter validation errors echo **field names only**, not values.

New stop conditions: `AgentLifecycle.begin_*` / `record_*`, not counters inside an agent class.
