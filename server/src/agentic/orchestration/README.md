# src/agentic/orchestration/ — Request Lifecycle Coordinator

Verified against the code on 2026-09-23.

## Purpose

`AIOrchestrator` (`orchestrator.py`) owns one chat turn end to end:
authorize → plan → execute → validate → aggregate → guardrail review →
build the response, writing compliance-log events along the way. It
**coordinates and never executes** agents or tools itself; execution is
delegated to `agentic/execution/` (`Executor`), which runs the plan as a
LangGraph graph whose nodes drive `agents/runtime/`.

## Entry points

| Method | Called by | What differs |
|---|---|---|
| `handle(request, action_workflow_service)` | `ChatService.chat()` | Non-streaming; returns one `OrchestratorResponse` |
| `stream(request, action_workflow_service)` | `ChatService.stream_chat()` | Same lifecycle; `Executor.execute_streaming()`; all chunks buffered until the guardrail verdict, then replayed or replaced |
| `resume(...)` | `HitlResumeService` after an approval decision | `Executor.resume()`; single guardrail pass, no regenerate loop |

Schemas: `schemas/request.py` (`OrchestratorRequest`, `Attachment`),
`schemas/context.py` (`OrchestrationContext`), `schemas/response.py`
(`OrchestratorResponse`, `OrchestratorStreamChunk`).

## Request flow (`handle()`)

```mermaid
sequenceDiagram
    autonumber
    participant CS as ChatService
    participant O as AIOrchestrator
    participant AZ as AuthorizationService<br/>(application/authorization)
    participant P as ExecutionPlanner<br/>(planning/)
    participant CL as ComplianceLogService
    participant X as Executor<br/>(execution/)
    participant V as ResponseValidator
    participant AG as ResponseAggregator
    participant G as OutputGuardrailService<br/>(guardrails/)

    CS->>O: handle(request)
    O->>AZ: authorize_request(user_id, message)<br/>TF-IDF capability analysis → RBAC check_intent
    O->>P: create_plan(context)
    O->>CL: record_plan_created(intent, mode, step_count)
    loop attempt 1..guardrail_max_regenerate_attempts+1
        O->>X: execute(conversation, plan, context)
        X-->>O: ExecutionResultSchema (state, artifacts, action, approval)
        alt no FINAL/NEED_INPUT agent response
            O-->>CS: generic "wasn't able to complete" response (+ action/approval if any)
        end
        O->>V: validate(agent_responses)
        O->>AG: aggregate(agent_responses)
        O->>CL: record_agent_decision(groundedness, relevance) per response
        O->>G: review(content, evidence_text)
        opt action != NONE
            O->>CL: record_guardrail_fired(...)
        end
        alt BLOCKED and attempts remain
            Note over O: regenerate with thread_id ":guardrail-retry-N"
        else NONE / FLAGGED / REDACTED / out of attempts
            Note over O: exit loop
        end
    end
    O-->>CS: OrchestratorResponse (content, citations, sources, usage, guardrail, action, approval)
```

A final `BLOCKED` verdict returns a fixed refusal instead of the
generated content.

## `stream()` differences

- Each attempt's `AgentStreamChunkDTO`s are **buffered**, never forwarded,
  until the loop resolves, so a discarded attempt never reaches the client.
- NONE/FLAGGED: buffered chunks are replayed, then one empty
  `is_final=True` chunk carries the `OrchestratorResponse`.
- REDACTED/BLOCKED: chunks are dropped and one `is_final=True` chunk
  carries the redacted text or the refusal.

## Notes

- `authorize_request` runs a TF-IDF capability analysis of the message and,
  when capabilities are found, an RBAC intent check
  (`application/authorization/`, policy from
  `application/authorization/rbac/policy.py`).
- When execution returns no FINAL/NEED_INPUT agent response, `handle()`
  returns a fixed fallback message together with any pending
  action/approval.
- The compliance log's `tenant_id` is set to the user id.
