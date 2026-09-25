# src/agentic/policy/ — Per-Agent Tool and Delegation Policy

Verified against the code on 2026-09-23. This is agent-level least
privilege ("which tools may agent X call"). User-level authorization
(RBAC, capability analysis, approvals) is separate, in
`application/authorization/`.

## Components

| File | Class | Role |
|---|---|---|
| `schemas.py` | `AgentPolicy(agent_id, allowed_tools, allowed_agents, allow_delegation, require_citations)`, `PolicyCheckResult` | Immutable policy + allow/deny result |
| `agent_policy.py` | `DatabaseAgentPolicyProvider` | Production provider: one `agent_policies` row per agent, fresh session per `get_policy()`; missing or disabled row → `AgentPolicyNotFoundError` |
| `agent_policy.py` | `StaticAgentPolicyProvider` | In-memory provider (not wired in production) |
| `guard.py` | `AgentPolicyGuard` | `check_tool()`, `check_delegation()`, `check_citations()` |
| `tool_permission.py` | `ToolPermissionGuard` | `tool_name in policy.allowed_tools` |
| `tool_catalog.py` | `AgentToolCatalog` | `describe(agent_id)`: the agent's policy → `ToolRegistry.describe()`; gives an agent handling a collaboration message its own tools |

Seeding: `wiring/factories/agent_policies.py` writes defaults at startup
(`main.py` lifespan): `legal` → `retriever`, `case_law_search` (+
`web_research` when enabled in settings); `contract` → `retriever`,
`library_lookup`. No agent gets `email` or `slack`. The agent's prompt
lists exactly these tools (the ones that are registered and
agent-callable) with their parameter schemas.

## Flow

```mermaid
sequenceDiagram
    autonumber
    participant AE as AgentExecution.start()
    participant DB as DatabaseAgentPolicyProvider
    participant H as AgentExecutionHandle
    participant C as AgentContinuationService
    participant G as AgentPolicyGuard

    AE->>DB: get_policy(agent_id)
    DB-->>AE: AgentPolicy (allowed_tools from the agent_policies row)
    H->>G: check_tool(policy, tool_name) on every LLM-proposed TOOL_CALL
    G-->>H: denied → the model is told which tools it may use and asked again<br/>(once, by default); then FAILED_POLICY
    C->>G: check_tool(policy, "retriever") before the forced corrective retrieval
    H->>G: check_delegation(policy, target) on DELEGATE
```

---

Known architecture and security gaps are tracked privately by the maintainers.
