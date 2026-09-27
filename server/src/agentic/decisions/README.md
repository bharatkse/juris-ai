# src/agentic/decisions/ — The Agent Decision Contract

Verified against the code on 2026-09-23.

## Purpose

Defines what an agent may return from one reasoning step and rejects
malformed decisions before the runtime acts on them.

| File | Contents |
|---|---|
| `decision.py` | `AgentDecisionType`: `final`, `tool_call`, `delegate`, `need_input`, `fail` |
| `schemas.py` | `AgentDecision` (Pydantic; the `response_model` for `BaseAgent._reason()`), `AgentToolCall(tool_name, parameters: dict)`, `AgentDelegation`, `AgentUserInputRequest`, `AgentFailure` |
| `validator.py` | `AgentDecisionValidator.validate()`: per-type required payload, and every other payload must be empty |

## Flow

```mermaid
flowchart TD
    LLM["BaseAgent._reason()<br/>LLM structured output → AgentDecision"] --> V["AgentDecisionValidator.validate()<br/>(built in execution/graph/factory.py,<br/>called in AgentExecutionHandle.reason())"]
    V --> T{decision_type}
    T -->|final| F["final_response non-blank"]
    T -->|tool_call| TC["tool_call present"]
    T -->|delegate| DG["delegation present"]
    T -->|need_input| NI["user_input present"]
    T -->|fail| FA["failure present"]
    F & TC & DG & NI & FA --> O{"any other payload set?"}
    O -->|yes| ERR["AgentDecisionValidationError"]
    O -->|no| OK["valid decision → _handle_decision()"]
```

---

Known architecture and security gaps are tracked privately by the maintainers.
