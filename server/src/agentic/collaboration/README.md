# src/agentic/collaboration/ — Agent-to-Agent Messaging (DELEGATE)

Verified against the code on 2026-09-23. Delegation is disabled by
default: no agent policy grants `allow_delegation`.

## Purpose

`CollaborationBus` (`bus.py`) routes an `AgentMessageSchema` to the
recipient agent's `handle_message()`, which performs **one** reasoning
step (no tools, no further delegation) and returns its `AgentDecision` to
the delegating agent.

Both `legal` and `contract` are registered on the bus at startup
(`wiring/factories/agents.py:74-80`); the bus is created once in
`wiring/composition.py:54`.

## Flow

```mermaid
sequenceDiagram
    autonumber
    participant H as AgentExecutionHandle
    participant G as AgentPolicyGuard
    participant C as AgentContinuationService._delegate()
    participant B as CollaborationBus
    participant T as Target BaseAgent

    H->>G: check_delegation(policy, target_agent_id)
    G-->>H: allowed / denied per AgentPolicy
    Note over H,T: the steps below only run if delegation is allowed
    C->>B: send(AgentMessageSchema(recipient, payload{request, parameters}))
    B->>T: handle_message(message)
    T->>T: one _reason() call with the delegated request
    T-->>C: AgentDecision (returned as a bare object)
    C->>H: extend_reasoning_context(...), reason() again
```

---

Known architecture and security gaps are tracked privately by the maintainers.
