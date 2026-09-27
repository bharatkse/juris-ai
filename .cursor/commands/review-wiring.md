# Review wiring and dead paths

Find features that exist in code but are never composed, plus sibling-module asymmetries. Scope: $ARGUMENTS (default: whole `server/src/`).

## Method

1. Start at `wiring/composition.py` and every `wiring/factories/*.py`. List objects constructed and registered (`register_tools`, `register_agents`, `create_planner`, `create_executor`, MCP URLs, seeders).
2. For each `Tool` subclass, `BaseAgent` subclass, application service, and `adapters/clients/**` class, grep for construction **outside tests**. Flag if only defined or only tested.
3. Compare siblings:
   - `agentic/agents/runtime/` vs `agentic/tools/runtime/` (interrupt/policy/lifecycle live only on the agent side by design — flag accidental duplication or a tool that bypasses `ToolExecutionService`).
   - `check_intent` vs `check_action` vs `AgentPolicyGuard.check_tool`.
   - `StaticAgentPolicyProvider` vs `DatabaseAgentPolicyProvider` (which one does `create_executor` inject?).
   - `BraveClient` vs `SearXNG` (`wiring/factories/search.py`).
   - `CollaborationBus` / `DELEGATE` / `check_delegation` vs production `allow_delegation`.
4. Stale comments: `core.request_context` (module is `application.context.request`); `RetrieverTool` `allowed_document_ids`; `LegalAgent.inference_task = FACTUAL_ANSWER` vs `_reason()` using `STRUCTURED_DECISION`; `LegalAgent.metadata.tools`.
5. `api/v1/endpoints/*` vs `wiring` vs `api/dependencies/` — route exists but service never injected, or factory builds something no route uses.

## Output

- Dead / unwired (path + evidence).
- Asymmetries (intentional vs bug).
- Stale docs/comments.
- Suggested wiring or deletion. Do not edit unless asked.
