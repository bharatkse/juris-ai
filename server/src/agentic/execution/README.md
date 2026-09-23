# src/agentic/execution/ — Executing a Validated Plan

## Purpose

`execution/` runs an already-validated `ExecutionPlanDTO` to completion.
It owns **coordination**, not **reasoning**: it decides which step runs
when (derived from `depends_on`, not `execution_mode` — see below),
drives each step through LangGraph, and assembles the collected agent
responses into one `OrchestratorResponse`. It does not create plans
(`planning/`), decide agent-level `TOOL_CALL`/`FINAL`/`DELEGATE`
reasoning (`agents/`), or perform authorization/approval
(`application/`, `agentic/policy/`).

Read this after `planning/README.md` (the plan this package consumes)
and alongside `agents/runtime/README.md` (what actually runs inside each
graph node) — this file is the layer in between.

## Entry points

| Class | File | Called by |
|---|---|---|
| `Executor` | `executor.py` | `AIOrchestrator` (`orchestration/orchestrator.py`) — the only caller |
| `ExecutionSession` | `session.py` | `Executor`, once per call (request-scoped, not reused) |
| `ExecutionGraphFactory` | `graph/factory.py` | `ExecutionSession`, to build+compile the LangGraph graph for this plan |
| `ExecutionGraphBuilder` | `graph/builder.py` | `ExecutionGraphFactory` — stateless, translates `depends_on` into LangGraph edges |
| `AgentExecutionNode` | `graph/nodes.py` | LangGraph itself, once per graph node (= once per plan step) |
| `ResponseValidator` | `validation/response.py` | `AIOrchestrator` (injected in `wiring/composition.py:93`), after `Executor` returns |
| `ResponseAggregator` | `aggregation/response.py` | `AIOrchestrator` (injected in `wiring/composition.py:94`), after validation passes |
| `ExecutionSession._finish()` / `_prepare_action()` | `session.py` | every run and resume: forwards a pending action through `ActionWorkflowService` (RBAC + approval creation), sets `WAITING_FOR_APPROVAL`, assembles state/memory |
| `AgentResponseMapper` | `aggregation/mapper.py` | `AgentExecutionNode`, per FINAL/NEED_INPUT step, to build the per-step `AgentResponseDTO` |
| `ExecutionStateAssembler` | `state/assembler.py` | `ExecutionSession`, to build/read `ExecutionGraphState` |

`Executor` exposes three methods, all delegating to a fresh
`ExecutionSession`:

- `execute()` — normal, non-streaming run; returns one `ExecutionResultSchema`.
- `execute_streaming()` — same graph, but yields `AgentStreamChunkDTO`
  items as they're produced, then exactly one `ExecutionResultSchema`
  as the final item. Only the plan's `FINAL` step ever streams (see
  `graph/nodes.py::_stream_final_answer_if_reached`) — a multi-step
  plan streams at most once, for whichever step reaches `FINAL`.
- `resume()` — resumes a LangGraph run paused mid-graph by a gated
  tool call (`email`/`slack`, via `interrupt()`). One exception to
  "Executor doesn't decide business rules": actually invoking the
  now-approved tool happens *here*, once, before the graph resumes —
  not inside the replayed node, because LangGraph replays a resumed
  node's whole function body from the top, and a tool call must not
  run twice. See `AgentContinuationService._execute_gated_tool()`'s
  docstring (`agents/runtime/continuation.py`) for the full hazard and
  `_call_replay_safe()`'s checkpointing fix for ordinary (ungated)
  tool calls in the same turn.

## Request flow

```mermaid
flowchart TD
    ORCH[AIOrchestrator] --> EXEC["Executor.execute() /<br/>execute_streaming() / resume()"]
    EXEC --> SESSION["ExecutionSession<br/>(session.py, request-scoped)"]
    SESSION --> ASSEMBLE["ExecutionStateAssembler<br/>builds initial ExecutionGraphState"]
    SESSION --> FACTORY["ExecutionGraphFactory.create()<br/>(graph/factory.py)"]
    FACTORY --> BUILDER["ExecutionGraphBuilder.build()+compile()<br/>(graph/builder.py)<br/>topology = plan.steps[*].depends_on"]
    BUILDER --> GRAPH["Compiled LangGraph<br/>(Postgres checkpointer attached)"]
    GRAPH -->|per step, once dependencies COMPLETED| NODE["AgentExecutionNode.__call__()<br/>(graph/nodes.py)"]
    NODE --> AEXEC["AgentExecution.start() -> .reason()<br/>(agents/runtime/execution.py)"]
    AEXEC --> CONT["AgentContinuationService.execute()<br/>(agents/runtime/continuation.py)<br/>handles TOOL_CALL loop + _gate_final"]
    CONT --> NODE
    NODE -->|streaming session, FINAL step only| STREAMWRITER["get_stream_writer()<br/>chunks yielded to caller"]
    NODE -->|FINAL / NEED_INPUT| MAPPER["AgentResponseMapper.map()<br/>(aggregation/mapper.py)<br/>builds AgentResponseDTO incl. citations/sources"]
    MAPPER --> STATE["ExecutionGraphState<br/>memory_updates / execution_state_updates"]
    GRAPH -->|all steps resolved, or interrupt() for a gated tool| FINISH["ExecutionSession._finish()"]
    FINISH --> PREP["_prepare_action()<br/>ActionWorkflowService: RBAC authorize_action,<br/>create Approval, status WAITING_FOR_APPROVAL"]
    PREP --> RESULT["ExecutionResultSchema<br/>(state, artifacts, action, approval)"]
    RESULT --> EXEC
    EXEC --> ORCH
    ORCH --> VALIDATOR["ResponseValidator.validate()<br/>(validation/response.py, called by AIOrchestrator)<br/>non-empty, unique-per-agent, non-empty content"]
    VALIDATOR --> AGG["ResponseAggregator.aggregate()<br/>(aggregation/response.py, called by AIOrchestrator)<br/>merges content/citations/sources/metadata"]
```

## Concurrency: derived from `depends_on`, not `execution_mode`

`ExecutionPlanDTO.mode` (`SEQUENTIAL`/`PARALLEL`/`HYBRID`) is recorded
for telemetry only — nothing in this package branches on it.
`ExecutionGraphBuilder._add_edges()` derives the actual LangGraph
topology purely from each step's `depends_on`:

- No `depends_on` → edge from `START` (runs concurrently with any
  other step that also has none).
- One dependency → edge from that step.
- Multiple dependencies → a LangGraph multi-edge; the step only
  becomes eligible once *all* listed dependencies have a `COMPLETED`
  status (`ExecutionGraphBuilder._dependencies_completed()` — `PARTIAL`,
  `FAILED`, and `SKIPPED` do not satisfy it, and an unsatisfied step is
  itself marked `SKIPPED`, not blocked forever).
- A step nothing depends on gets an edge to `END`.

Because two steps with no dependency relationship between them (in
either direction) are free to start at the same time, **the same
agent must never be assigned to two such steps** — `planning/validator.py`
(`ExecutionPlanValidator._validate_agent_concurrency`) now rejects that
shape before this package ever sees the plan. Before that fix existed,
this was exactly how `DuplicateAgentResponseError` reached
`ResponseValidator._validate_unique_agents` in production: both steps'
graph nodes ran concurrently, both agent calls succeeded individually,
and only the post-execution uniqueness check caught the conflict —
after two real LLM calls had already run. See `planning/validator.py`
for the fix; this package's own defenses (`ResponseValidator`) remain
as a second, independent backstop, not the primary guard.

## Runtime state ownership

Three runtime objects live for the duration of one `ExecutionSession`
(graph nodes must not construct or mutate these directly — they only
return the update dicts `graph/nodes.py` builds):

- **`ExecutionGraphState`** (`graph/state.py`) — the LangGraph state
  dict itself: `execution_state_updates` (append-only step status
  history — see `ExecutionGraphBuilder._latest_step_statuses()`,
  which resolves "latest" by walking this list in reverse rather than
  overwriting in place), `agent_decision_updates`, `memory_updates`,
  `reasoning_context`, `conversation`, `context`, `streaming`.
- **`ExecutionMemory`** (`schemas/memory.py`) — step results, retrieved
  content, entities, and other intermediate artifacts a later step's
  agent may read via `reasoning_context`.
- **`ExecutionStateAssembler`** (`state/assembler.py`) — builds the
  initial `ExecutionGraphState` for a fresh run (`assemble_state`) and
  reads back `ExecutionMemory`/action state after the graph finishes
  (`assemble_memory`, `assemble_action`).

## Validation and aggregation

Both classes live in this package but are **called by `AIOrchestrator`**,
not by `ExecutionSession`. `ResponseValidator` (`validation/response.py`) runs once,
after `Executor` returns, on the flat list of `AgentResponse`s the
orchestrator extracted from the result's artifacts:

1. `EmptyResponseError` if the list is empty.
2. `DuplicateAgentResponseError` if the same `agent_name` appears twice
   — see the concurrency section above for why this can only still
   happen if `planning/validator.py`'s own guard is somehow bypassed;
   treat a hit here as a real bug, not routine.
3. `EmptyContentError` if any response's `content` is blank.

`ResponseAggregator` (`aggregation/response.py`) then merges the
validated responses' content, citations, sources, and metadata into
one `OrchestratorResponse` — it does not re-derive or paraphrase
anything; citations/sources are carried through verbatim from what
`AgentResponseMapper` already built per step. By design,
`RetrievedContentDTO` must survive unmodified from the tool call
through the agent's prompt builder into `AgentResponseDTO`, and from
there into this aggregator's `sources`/`citations` output — never let
an agent regenerate or paraphrase source metadata from the LLM output.

---

Known architecture and security gaps are tracked privately by the maintainers.
