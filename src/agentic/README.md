# src/agentic/ — Planning, Orchestration, Execution, Agents, Tools

Read `src/agentic/CLAUDE.md` alongside this file: that one is the
terse dev-workflow reference (checklists, request-flow order); this
one documents the real current architecture in more depth, with
diagrams, for someone debugging a production issue six months from
now. Where they'd disagree, `CLAUDE.md` wins for day-to-day work and
this file should be corrected.

## Module map

| Path | Responsibility |
|---|---|
| `planning/` | Intent analysis, `ExecutionPlan` generation (template-based or LLM-based) |
| `orchestration/` | `AIOrchestrator` — coordinates the request lifecycle; never executes agents/tools itself |
| `execution/` | `Executor`, LangGraph graph construction/compilation, execution state/memory, response aggregation |
| `agents/` | Domain reasoning (`LegalAgent`, `ContractAgent`), prompt building, token budgeting, agent runtime (lifecycle, continuation) |
| `evaluation/` | `AnswerEvaluator` + `AnswerQualityPolicy` — post-hoc answer quality gating (groundedness/relevance/correctness/citations) |
| `policy/` | `AgentPolicyProvider`/`AgentPolicyGuard`/`ToolPermissionGuard` — what tools an agent may call |
| `registry/` | Agent and tool lookup by name |
| `tools/` | External actions: retrieval, web search, case-law search, document parsing, messaging |
| `collaboration/` | `CollaborationBus` — mediated agent-to-agent messaging (DELEGATE decisions). **Unverified/unexercised as of this writing**: no test or production path drives an actual end-to-end delegation; `DELEGATE` is only reachable if an agent's LLM emits that decision type, and nothing in the current prompt-driven flow does so routinely. Treat as present-but-unproven, not present-and-working. |
| `decisions/` | `AgentDecision`/`AgentDecisionType` schemas + validator — the structured contract an agent's LLM call must return |

## Request lifecycle (real, graph-based path)

This is the path every real chat request takes. It is **not** the
`BaseAgent.run()`/`stream()` methods — those exist on `BaseAgent` but
are dead code, unreached from this path (see Known gaps).

```mermaid
flowchart TD
    REQ[ChatService] --> ORCH["AIOrchestrator.handle()<br/>(orchestration/orchestrator.py)"]
    ORCH -->|1. authorize| AUTH[AuthorizationService]
    ORCH -->|2. plan| PLAN["ExecutionPlanner -> LLMPlanGenerator<br/>(planning/llm_planner.py)<br/>temperature=0.0 (STRUCTURED_DECISION)"]
    PLAN --> EXECUTOR["Executor.execute()<br/>(execution/executor.py)"]
    EXECUTOR --> SESSION["ExecutionSession<br/>-> ExecutionGraphFactory.create()"]
    SESSION --> GRAPH["Compiled LangGraph<br/>(execution/graph/builder.py)<br/>topology derived from step.depends_on"]
    GRAPH --> NODE["AgentExecutionNode<br/>(execution/graph/nodes.py)"]
    NODE --> AEXEC["AgentExecution.start()<br/>(agents/runtime/execution.py)<br/>resolves AgentPolicy via DatabaseAgentPolicyProvider"]
    AEXEC --> AGENT["Agent.reason()<br/>(LegalAgent / ContractAgent)<br/>temperature=0.2 (FACTUAL_ANSWER)"]
    AGENT --> DECISION{AgentDecision}
    DECISION -->|TOOL_CALL| GUARD["AgentPolicyGuard.check_tool()"]
    GUARD -->|allowed| TOOLREG["Tool Registry -> Tool.execute()"]
    GUARD -->|denied| FAILPOLICY[FAILED_POLICY termination]
    TOOLREG --> CONT["AgentContinuationService<br/>(agents/runtime/continuation.py)<br/>feeds result back, re-reasons"]
    CONT --> AGENT
    DECISION -->|DELEGATE| BUS["CollaborationBus.send()<br/>(unverified path, see module map)"]
    BUS --> CONT
    DECISION -->|FINAL| GATE["_gate_final()<br/>AnswerQualityPolicy check<br/>(see sequence diagram below)"]
    GATE --> MAPPER["AgentResponseMapper.map()<br/>(execution/aggregation/mapper.py)<br/>builds citations/sources from reasoning_context"]
    MAPPER --> VALIDATOR[ResponseValidator]
    VALIDATOR --> AGG["ResponseAggregator<br/>(execution/aggregation/response.py)"]
    AGG --> ORCH
    ORCH --> REQ
```

## FINAL-decision quality gate

`AgentContinuationService._gate_final()` evaluates every proposed
FINAL answer before accepting it. The two branches below are the only
two remedies the code has — which one runs depends on *which* quality
check failed.

```mermaid
sequenceDiagram
    participant Agent
    participant Continuation as AgentContinuationService
    participant Evaluator as AnswerEvaluator
    participant Policy as AnswerQualityPolicy
    participant Guard as AgentPolicyGuard
    participant Tool as retriever Tool

    Agent->>Continuation: FINAL decision (answer)
    Continuation->>Evaluator: evaluate(question, answer, evidence)
    Evaluator-->>Continuation: groundedness, relevance,<br/>completeness, correctness
    Continuation->>Policy: is_sufficient(evaluation)

    alt sufficient (groundedness/relevance hard gates pass;<br/>completeness advisory-only)
        Policy-->>Continuation: True
        Continuation-->>Agent: accept FINAL, build response
    else groundedness or relevance failed
        Policy-->>Continuation: False
        Continuation->>Guard: check_tool(policy, "retriever")
        Note over Guard: same check an LLM-proposed<br/>TOOL_CALL would get -- closed this<br/>session, previously bypassed
        alt allowed
            Guard-->>Continuation: allowed
            Continuation->>Tool: execute(query, top_k=8)
            Tool-->>Continuation: fresh evidence
            Continuation->>Agent: re-reason with new evidence
        else denied or tool unavailable
            Guard-->>Continuation: denied
            Continuation->>Agent: weak re-ask (feedback note,<br/>no new evidence)
        end
    else only correctness or citation failed
        Policy-->>Continuation: False
        Note over Continuation: more retrieval isn't the right<br/>remedy for these -- no retry loop
        Continuation->>Agent: weak re-ask (feedback note,<br/>no new evidence)
    end
```

Corrective retrieval (`CORRECTIVE_RETRIEVAL_TOP_K = 8`, broader than a
normal `retriever` call's default `top_k=5`) was added this session —
it is not part of the original design and does not appear in
`docs/architecture/overview.md`'s diagrams.

## Rate limiting and token quota

Enforced per-user, via FastAPI dependency (not ASGI middleware —
middleware runs before auth resolves a user). Both `/chat` and
`/chat/stream` carry the same `enforce_usage_limits` dependency.

```mermaid
sequenceDiagram
    participant Client
    participant Endpoint as POST /chat
    participant Dep as enforce_usage_limits
    participant Usage as UsageService
    participant DB as usage_records (atomic upsert)
    participant Chat as ChatService
    participant Orch as AIOrchestrator

    Client->>Endpoint: request (+ JWT)
    Endpoint->>Dep: Depends(get_current_user) then Depends(enforce_usage_limits)
    Dep->>Usage: check_and_enforce(user_id)
    Usage->>DB: increment_request_count(minute window)
    DB-->>Usage: count
    alt count > REQUESTS_PER_MINUTE
        Usage-->>Endpoint: raise RateLimitExceededError
        Endpoint-->>Client: 429
    else
        Usage->>DB: get_daily_token_usage(day window)
        DB-->>Usage: daily_usage
        alt daily_usage >= DAILY_TOKEN_QUOTA
            Usage-->>Endpoint: raise TokenQuotaExceededError
            Endpoint-->>Client: 429
        else within limits
            Usage-->>Dep: pass (request already counted)
            Dep-->>Endpoint: continue
            Endpoint->>Chat: chat(...)
            Chat->>Orch: handle(...)
            Orch-->>Chat: result (result.usage = real provider-reported tokens)
            Chat->>Usage: record(user_id, input_tokens, output_tokens)
            Note over Usage: best-effort -- swallows its own<br/>errors, never fails an otherwise-<br/>successful response
            Usage->>DB: increment_tokens(day window)
            Chat-->>Endpoint: response
            Endpoint-->>Client: 200
        end
    end
```

**`/chat/stream` caveat, stated plainly**: the rate-limit dependency
runs identically for both endpoints, so a request that would be
blocked is blocked before either path starts. But the post-dispatch
`record()` step above only runs on the non-streaming path
(`ChatService.chat()`) — `ChatService.stream_chat()` has no equivalent
call, because `AIOrchestrator.stream()` doesn't exist (see Known
gaps) and the streaming endpoint is broken independent of rate
limiting. This was a deliberate, explicit deferral, not an oversight —
fixing `/chat/stream` is separate, tracked work.

## `agent_policies` and tool authorization

Real DB table (`agent_policies`: `agent_id` unique, `allowed_tools`
JSON list, `enabled` bool), resolved through
`DatabaseAgentPolicyProvider` (`policy/agent_policy.py`) — a
process-lifetime singleton that opens a fresh DB session per
`get_policy()` call rather than holding one bound session across
concurrent requests. Replaces a static `AGENT_POLICIES = {}` dict that
used to make every real agent execution crash (not just "inert" — see
`claude.md` → Known gaps for that correction).

Seeded at startup (`main.py`'s `lifespan()` ->
`wiring/factories/agent_policies.py::seed_default_agent_policies()`,
idempotent upsert):

```python
{
    "legal": ["retriever", "case_law_search"],       # + "web_research" if enabled, see below
    "contract": ["retriever", "parser", "library_lookup"],
}
```

**`web_research` feature flag**: `settings.agent_policy
.ENABLE_WEB_RESEARCH_FOR_LEGAL` (default `False`, env var
`ENABLE_WEB_RESEARCH_FOR_LEGAL`, `config/agent_policy.py`) gates
whether the `legal` agent's default policy includes `web_research`.
Off by default deliberately: it's a broad, open-internet capability
with no production track record — the enforcement path that makes
this grant meaningful (real `AgentPolicyGuard` checks) was only fixed
this session. Flip it once `web_research` has been observed under real
traffic, or grant it directly in `DEFAULT_AGENT_POLICIES` for a
specific deployment.

This is a first-cut seed, not derived from a specification — treat it
as a starting point to adjust, not a settled design.

## Temperature / determinism conventions

Every LLM call in this package resolves its sampling config through
`core.dto.inference.InferencePolicy.resolve(task, ...)` rather than
leaving a provider default in place — the one deliberate exception
being agent-facing prose generation, which stays non-zero on purpose.

| Call site | `LLMTask` | Temperature | Why |
|---|---|---|---|
| Planning (`planning/llm_planner.py`) | `STRUCTURED_DECISION` | `0.0` | Produces a structured `ExecutionPlan` consumed programmatically — no reason for run-to-run variance. |
| Agent tool-call/structured decisions (`agents/base.py._reason()`) | `STRUCTURED_DECISION` | `0.0` | Same reasoning — a `TOOL_CALL`/`FINAL` decision is a structured contract, not prose. |
| Agent final-answer generation (`agents/base.py`, `legal.py`, `contract.py`) | `FACTUAL_ANSWER` | `0.2` | Deliberately non-zero: user-facing legal/contract prose, small variance tolerated. Confirmed deliberate this session, left unchanged. |
| Conversation summarization (`application/services/conversation_summarization.py`) | `SUMMARIZATION` | `0.3` | Low but non-zero; consistency matters more than creativity, but summarizing prose isn't a structured decision either. |
| LLM-as-judge — faithfulness/relevancy/context precision-recall (`wiring/factories/evaluation.py::build_llm_judge`) | *(none — direct `LLMInferenceConfig`)* | `0.0` | **Fixed this session** — previously had no inference config at all, silently defaulting to an ambient `0.2`. Judge calls must be reproducible for `AnswerQualityPolicy`'s empirically calibrated thresholds (`agentic/evaluation/answer.py`) to keep meaning anything over time. |

Everything routes through `InferencePolicy` deliberately: it's the one
place a task's sampling intent is declared, instead of relying on
whatever a provider or dataclass default happens to be.

## Known gaps

Cross-referencing `claude.md` → Known gaps (repo-wide) rather than
duplicating it. Agentic-specific items:

- **`/chat/stream` is broken**: `ChatService.stream_chat()`
  (`application/services/chat.py`) calls `self._orchestrator.stream(
  ...)`, but `AIOrchestrator` (`orchestration/orchestrator.py`) has no
  `stream()` method — only `handle()`. Any real request to
  `POST /chat/stream` raises `AttributeError` server-side. Known,
  explicitly deferred (not part of this session's rate-limiting work
  — see the caveat above). Rate-limiting still applies to this
  endpoint regardless, so it is not a quota bypass, just broken.
- **`CollaborationBus`/`DELEGATE` is unverified** — see the module map
  entry above. Real code path, zero real exercise.
- **Citation-quality thresholds are uncalibratable from this dataset**
  — see `src/rag/README.md` → Known gaps and
  `agentic/evaluation/answer.py`'s `AnswerQualityPolicy` docstring for
  the full, honest accounting.
- **Tool-permission enforcement's remaining bypass** (`agents/base.py
  ._retrieve_context()`, dead code, now higher-risk since real
  enforcement exists elsewhere) and **the `Tool.execute() -> str`
  boundary losing structured per-result data** — both fully described
  in `claude.md` → Known gaps; not repeated here.
