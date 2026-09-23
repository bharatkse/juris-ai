# Architecture

## 1. Juris AI Architecture

```
                                      ┌──────────────────────┐
                                      │        CLIENT        │
                                      │   React / API User   │
                                      └──────────┬───────────┘
                                                 │
                                      HTTP / SSE / Multipart
                                                 │
                                                 ▼
                              ┌─────────────────────────────────┐
                              │          FASTAPI API            │
                              │                                 │
                              │ Auth / Validation / Streaming   │
                              │ Request Context / Rate Limit    │
                              └────────────────┬────────────────┘
                                               │
                                               ▼
                              ┌───────────────────────────────────┐
                              │          CHAT SERVICE             │
                              │                                   │
                              │ Conversation lifecycle            │
                              │ User/Assistant event persistence  │
                              │ Transaction boundary              │
                              │ Streaming                         │
                              └────────────────┬──────────────────┘
                                               │
                                               ▼
                    ╔════════════════════════════════════════════════╗
                    ║              AI ORCHESTRATOR                   ║
                    ║                                                ║
                    ║  Coordinates the AI request lifecycle          ║
                    ║  DOES NOT execute agents                       ║
                    ╚═══════════════════════╤════════════════════════╝
                                            │
                                            ▼
                              ┌─────────────────────────┐
                              │         PLANNER         │
                              │                         │
                              │ Intent Analysis         │
                              │ Context Analysis        │
                              │ Plan Generation         │
                              │ Plan Validation         │
                              └────────────┬────────────┘
                                           │
                                ┌──────────┴──────────┐
                                │                     │
                                ▼                     ▼
                         Template Plan          Planner LLM
                         (known intent)        (complex intent)
                                │                     │
                                └──────────┬──────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │      EXECUTION PLAN     │
                              │                         │
                              │ execution_mode          │
                              │ steps[]                 │
                              │ dependencies            │
                              │ agent                   │
                              │ input                   │
                              └────────────┬────────────┘
                                           │
                                           ▼
                    ╔════════════════════════════════════════════════╗
                    ║                    EXECUTOR                    ║
                    ║                                                ║
                    ║  Executes ExecutionPlan                        ║
                    ║  DOES NOT decide what to execute               ║
                    ╚═══════════════════════╤════════════════════════╝
                                            │
                          Resolve execution strategy
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               │                            │                            │
               ▼                            ▼                            ▼
         ┌─────────────┐              ┌─────────────┐              ┌─────────────┐
         │ SEQUENTIAL  │              │  PARALLEL   │              │    HYBRID   │
         │             │              │             │              │             │
         │ A → B → C   │              │ A ─┐        │              │ A → ┬─ B    │
         │             │              │ B ─┼→ C     │              │     └─ C    │
         └──────┬──────┘              │ C ─┘        │              │       → D   │
                │                     └──────┬──────┘              └──────┬──────┘
                └────────────────────────────┼────────────────────────────┘
                                             │
                                             ▼
                                  ┌────────────────────┐
                                  │    EXECUTION STEP  │
                                  └─────────┬──────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │  AGENT REGISTRY  │
                                   └────────┬─────────┘
                                            │
                         ┌──────────────────┼──────────────────┐
                         │                  │                  │
                         ▼                  ▼                  ▼
                    LegalAgent       ContractAgent       Future Agents
                         │                  │
                         └──────────────────┘
                                   │
                                   ▼
                         ╔══════════════════════╗
                         ║       AGENT          ║
                         ║                      ║
                         ║ Domain reasoning     ║
                         ║ Prompt construction  ║
                         ║ LLM interaction      ║
                         ╚══════════╤═══════════╝
                                    │
                           Optional retrieval
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    TOOL REGISTRY     │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼───────────────────┐
                 │                  │                   │
                 ▼                  ▼                   ▼
             Retriever            Search             Parser
                 │                  │                   │
                 │                  ▼                   ▼
                 │              Brave/etc.       PDF/Documents
                 │
       ┌─────────┴───────────────────────────────────────────┐
       │                                                     │
       ▼                                                     ▼
 Uploaded Documents                                     Web Search
       │                                                     │
       ▼                                                     ▼
 Document Parser                                      Search Results
       │                                                     │
       └──────────────────────┬──────────────────────────────┘
                              ▼
                    RetrievedContent[]
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
                 Content             Provenance
                                      │
                              source / title / url
                              provider / metadata
                                      │
                                      ▼
                              Prompt Builder
                                      │
                                      ▼
                              GenerateRequest
                                      │
                                      ▼
                           ┌────────────────────┐
                           │     LLM GATEWAY    │
                           └─────────┬──────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
                  Groq             OpenAI         Anthropic
                                     │
                                     ▼
                              AgentResponse
                                     │
                                     ▼
                           ExecutionMemory
                                     │
                                     ▼
                           ExecutionState
                                     │
                                     ▼
                              Next Step
                                     │
                                     ▼
                           Response Validator
                                     │
                                     ▼
                            Result Aggregator
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
                 Content          Sources         Citations
                    │                │                │
                    └────────────────┼────────────────┘
                                     ▼
                              AIResponse
                                     │
                                     ▼
                                ChatService
                                     │
                                     ▼
                                   FastAPI
                                     │
                              JSON / SSE
                                     │
                                     ▼
                                  CLIENT
```

## 2. The most important architectural separation

```
┌──────────────────────────────────────────────────────────┐
│                    AI ORCHESTRATOR                       │
│                                                          │
│ Planning + lifecycle coordination                        │
│                                                          │
│ ❌ Does not execute agents                               │
│ ❌ Does not execute tools                                │
│ ❌ Does not contain domain reasoning                     │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│                       EXECUTOR                           │
│                                                          │
│ Execution only                                           │
│                                                          │
│ ❌ Does not plan                                         │
│ ❌ Does not reason                                       │
│ ❌ Does not directly call tools                          │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│                        AGENTS                            │
│                                                          │
│ Domain reasoning                                         │
│                                                          │
│ LegalAgent                                               │
│ ContractAgent                                            │
│                                                          │
│ ❌ Do not execute other agents                           │
│ ❌ Do not directly call infrastructure                   │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│                         TOOLS                            │
│                                                          │
│ Actions / external capabilities                          │
│                                                          │
│ Retriever / Search / Parser / Database / etc.            │
└──────────────────────────────────────────────────────────┘
```

## 3. Two separate LLM responsibilities

```
                         USER REQUEST
                              │
                              ▼
                       ┌────────────┐
                       │  PLANNER   │
                       │    LLM     │
                       └─────┬──────┘
                             │
                             │ "What should we do?"
                             ▼
                       ExecutionPlan
                             │
                             ▼
                         EXECUTOR
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
             LegalAgent           ContractAgent
                  │                     │
                  ▼                     ▼
             ┌────────┐             ┌────────┐
             │  LLM   │             │  LLM   │
             └────────┘             └────────┘
                  │                     │
                  │ "How should       │
                  │  I answer?"       │
                  ▼                     ▼
             AgentResponse        AgentResponse
```

## 4. Retrieval architecture

```
                         LegalAgent
                             │
                             ▼
                       RetrieverTool
                             │
                 ┌───────────┼────────────┐
                 │           │            │
                 ▼           ▼            ▼
             Documents     Vector       Web
                 │          Search       Search
                 │            │            │
                 ▼            ▼            ▼
              Parser       Qdrant       Brave
                 │            │            │
                 └────────────┼────────────┘
                              │
                              ▼
                       Merge Results
                              │
                              ▼
                    RetrievedContent[]
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
              Content                 Provenance
                                        │
                            ┌───────────┼───────────┐
                            ▼           ▼           ▼
                          source      title         url
```

## 5. Provenance must survive the entire pipeline

```
Retriever
    │
    ▼
RetrievedContentDTO
    │
    ├── content
    └── source
          ├── name
          ├── title
          ├── url
          └── metadata
                │
                ▼
          Prompt Builder
                │
                ▼
             Agent
                │
                ▼
         AgentResponseDTO
                │
                ▼
          Aggregator
                │
        ┌───────┼────────┐
        ▼       ▼        ▼
      content sources citations
                │
                ▼
           AIResponse
                │
                ▼
              API
```

The LLM should **not be responsible for reconstructing source metadata.**

> **Implementation note:** a FINAL decision's `AgentResponseDTO` is
> built by `AgentResponseMapper.map()` (`execution/aggregation/mapper.py`),
> called from the graph's FINAL handling (`execution/graph/nodes.py`). It
> derives `CitationDTO`/`SourceDTO` values from the reasoning context
> accumulated during execution (`_build_provenance()`), and the
> Aggregator's merge step (`execution/aggregation/response.py`) combines
> them across agents.

## 6. Execution runtime

The Executor should own the runtime objects:

```
Executor
   │
   ├── ExecutionState
   │
   ├── ExecutionMemory
   │
   └── CollaborationBus
```

**ExecutionState**

```
step status
started_at
completed_at
failed_at
retry count
execution mode
current step
```

**ExecutionMemory**

```
step results
retrieved content
entities
intermediate artifacts
agent outputs
```

**CollaborationBus**

```
LegalAgent
    │
    ▼
CollaborationBus
    │
    ▼
ContractAgent
```

- `ExecutionState` tracks step status, retries, and execution
  progress.
- `ExecutionMemory` stores intermediate results and artifacts.
- `CollaborationBus` provides mediated agent-to-agent communication
  when collaboration is required.

> **Implementation note:** `ExecutionState`, `ExecutionMemory`,
> and `CollaborationBus` are implemented and owned by the Executor as
> shown. The `execution mode` field listed above is recorded and surfaced in telemetry
> (`execution/session.py`) but nothing branches on it. The
> SEQUENTIAL/PARALLEL/HYBRID shape in section 1's diagram is derived
> structurally from each step's `depends_on` graph
> (`execution/graph/builder.py`) — treat "execution mode" here as a
> descriptive label for that graph shape, not a switch the Executor
> reads.

### Corrective retrieval

When a FINAL answer fails groundedness or relevance
(`agentic/evaluation/answer.py`'s `AnswerQualityPolicy`),
`AgentContinuationService._gate_final()`
(`agents/runtime/continuation.py`) forces a real `retriever`
`TOOL_CALL` for the same question (broadened `top_k`) before letting
the agent try FINAL again, instead of only re-asking the same LLM with
a note and no new information. This system-initiated call goes through
`AgentPolicyGuard.check_tool()` exactly like an LLM-proposed one — an
agent without `"retriever"` in its policy cannot get this retry
either. Correctness/citation failures (the only other ways an answer
can fail the policy) still fall back to a weaker re-ask, since more
retrieval isn't the right remedy for those. See
`src/agentic/README.md` for the full sequence diagram.

## 7. Responsibility Matrix

Component Owns Must NOT own

```
| Component                    | Owns                          | Must NOT own            |
| ---------------------------- | ----------------------------- | ----------------------- |
| **FastAPI**                  | HTTP, auth, validation, SSE   | AI logic                |
| **ChatService**              | Conversation + DB transaction | Planning                |
| **Orchestrator**             | AI lifecycle coordination     | Agent execution         |
| **Planner**                  | Intent + ExecutionPlan        | Actual execution        |
| **Executor**                 | Plan execution                | Planning/reasoning      |
| **Agent**                    | Domain reasoning              | Infrastructure          |
| **Tool**                     | External action               | Domain reasoning        |
| **Agent Registry**           | Agent lookup                  | Agent execution         |
| **Tool Registry**            | Tool lookup                   | Tool execution          |
| **LLM Gateway**              | Provider abstraction          | Business logic          |
| **Aggregator**               | Merge outputs/provenance      | Planning                |
| **Validator**                | Validate results              | Generate answers        |
| **ExecutionMemory**          | Runtime artifacts             | Persistent conversation |
| **ConversationEventService** | DB event persistence          | AI execution            |
| **Observability**            | Logs/traces/metrics           | Business decisions      |

```

> **Implementation note:** the role boundaries above hold in code (the
> Orchestrator never executes agents/tools; the Executor never plans).
> Tool permissions are enforced by `AgentPolicyGuard.check_tool()`
> against the DB-backed `agent_policies` table
> (`DatabaseAgentPolicyProvider`, seeded at startup), for both
> LLM-proposed `TOOL_CALL`s (`agents/runtime/execution.py`) and the
> system-forced corrective retrieval (`agents/runtime/continuation.py`,
> see section 6). The Aggregator's "Merge outputs/provenance" row is
> implemented as described in the section 5 note.

---

## 8. Final Request Lifecycle

### Normal Question

```text
POST /chat
   │
   ▼
ChatService
   │
   ├── Create USER event
   │
   ▼
AIOrchestrator
   │
   ▼
Planner
   │
   │  LLM #1
   ▼
ExecutionPlan
   │
   ▼
Executor
   │
   ▼
LegalAgent
   │
   ├── RetrieverTool
   │      ├── Document
   │      ├── Vector
   │      └── Web
   │
   ├── PromptBuilder
   │
   └── LLM #2
   │
   ▼
AgentResponse
   │
   ▼
ExecutionState / Memory
   │
   ▼
ResponseValidator
   │
   ▼
Aggregator
   │
   ├── content
   ├── citations
   ├── sources
   ├── usage
   └── agents
   │
   ▼
OrchestratorResponse
   │
   ▼
ChatService
   │
   ├── Create ASSISTANT event
   │
   └── COMMIT
   │
   ▼
API Response
```

### Multiple Agents

```text
                         ExecutionPlan
                              │
                              ▼
                           Executor
                              │
                 ┌────────────┴────────────┐
                 │                         │
              LegalAgent             ContractAgent
                 │                         │
               LLM #2                    LLM #3
                 │                         │
                 └────────────┬────────────┘
                              │
                              ▼
                         Aggregator
                              │
                              ▼
                       Final Response
```

### Hybrid Execution

```text
             Step A
               │
               ▼
             Step B
               │
        ┌──────┴──────┐
        ▼             ▼
     Step C         Step D
        │             │
        └──────┬──────┘
               ▼
             Step E
```

---

## Core Architectural Rule

> **Orchestrator plans and coordinates. Executor executes. Agents
> reason. Tools act. Aggregator assembles. ChatService owns the
> conversation transaction.**

### LLM Responsibilities

There are intentionally multiple LLM calls:

1.  **Planner LLM (#1)** --- determines _what should be executed_ and
    produces an `ExecutionPlan`.
2.  **Agent LLM (#2+)** --- performs domain-specific reasoning for each
    execution step.

The Planner LLM and Agent LLM therefore have different responsibilities
and should remain separate.

### Execution Modes

The `ExecutionPlan` must preserve explicit execution-mode semantics:

- **Sequential** --- steps execute one after another.
- **Parallel** --- independent steps execute concurrently.
- **Hybrid** --- sequential dependency groups combined with parallel
  branches.

The Executor selects the appropriate execution strategy from the plan.
It does not redesign or reinterpret the plan.

> **Implementation note:** see the section 6 note above —
> `execution_mode` isn't read by the Executor; the actual strategy is
> derived from each step's dependencies.

### Persistence Boundary

`ChatService` owns the conversation-level transaction:

```text
ChatService
    │
    ├── create USER event
    │
    ├── execute orchestration
    │
    ├── create ASSISTANT event
    │
    └── COMMIT
```

`ConversationEventService` is responsible for event persistence only and
does not commit independently.

### Provenance

Retrieved information must preserve provenance through the pipeline:

```text
Retriever
    │
    ▼
RetrievedContent
    │
    ├── content
    └── source metadata
          │
          ▼
      Agent / Prompt
          │
          ▼
      AgentResponse
          │
          ▼
       Aggregator
          │
     ┌────┴────┐
     ▼         ▼
  Sources   Citations
```

This keeps source information available for the final API response.

> **Implementation note:** see the section 5 note above — `citations`/
> `sources` are populated by `AgentResponseMapper`.

---

## 9. Observability

### OTEL Collector

#### 1.0

```text
                    Juris-AI
                       │
                OpenTelemetry
                       │
                       ▼
                OTEL Collector
                  /          \
                 /            \
          Metrics              Traces
             │                   │
             ▼                   ▼
        Prometheus              Tempo
             │                   │
             └─────────┬─────────┘
                       ▼
                    Grafana
```

#### 2.0

```text
                    ┌──────────────┐
                    │   Grafana    │
                    │    :3000     │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │              │
                    ▼              ▼
              Prometheus        Tempo
                 :9090           :3200
                    ▲              ▲
                    │              │
                    │              │
              Metrics          Traces
                    │              │
                    └──────┬───────┘
                           │
                           │
                  OTEL Collector
                    :4317/:4318
                           ▲
                           │
                        Juris-AI
```

### LangSmith Trace

**LangSmith** handles the LangChain/LangGraph/LLM execution layer.

```text
                         Juris-AI
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
       OpenTelemetry                  LangSmith
             │                             │
             ▼                             ▼
      OTEL Collector                 LangSmith Cloud
          │       │
          │       │
          ▼       ▼
    Prometheus   Tempo
          │       │
          └───┬───┘
              ▼
           Grafana
```

LangSmith should capture

For your Juris-AI architecture, eventually we want LangSmith to show something like:

```text
Chat request
│
└── AIOrchestrator
    │
    ├── ExecutionPlanner
    │   └── LLM call
    │
    └── Executor
        │
        ├── Agent
        │   └── LLM call
        │
        └── Tool
```

This is different from your OTEL trace:

```
POST /api/v1/chat
└── juris_ai.orchestration
    └── juris_ai.planning
```

OTEL tells us system timing and distributed execution.

LangSmith tells us LLM/agent behavior.

---

Known architecture and security gaps are tracked privately by the maintainers.
