# Scaffold a new agent

Agent: $ARGUMENTS

Checklist from `server/src/agentic/CLAUDE.md` (do not skip wiring).

## Steps

1. `server/src/agentic/agents/<name>.py` — `@final` subclass of `BaseAgent` like `legal.py`. `metadata = AgentMetadataDTO(name=..., description=...)` **is planner routing text**. Do not list agents in `planning.md`.
2. `agents/prompts/<name>.py` + `agents/prompts/templates/<name>.md`. Planner prompts stay in `planning/prompts/`.
3. Add value to `AgentTypeEnum` (plan steps are constrained to it).
4. `wiring/factories/agents.py` — construct with the shared `build_agent_llm_client()`, `registries.agent_registry.register(component=...)`.
5. `wiring/factories/agent_policies.py` — `allowed_tools` seed (rewritten on startup). User RBAC is separate (`application/authorization/`).
6. Keyword templates in `planning/templates.py` if this agent should skip the planner LLM; ensure only one template matches.
7. `CollaborationBus` handler is added for every registered agent in `wiring/factories/executor.py` — do not add a second registration path.
8. Unit tests under `tests/unit/agentic/agents/` (prompt catalog includes policy tools). Agents reason only; no adapter calls.

`metadata.tools` on `LegalAgent` is stale vs policy seeds — do not copy that field as source of truth; grants live in `agent_policies`.
