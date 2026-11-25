# Scaffold a new tool

Name / behavior: $ARGUMENTS

Follow `server/src/agentic/tools/CLAUDE.md` and `.cursor/rules/agents-and-tools.mdc`. Do not invent a `dry_run()` method.

## Steps

1. Add `server/src/agentic/tools/<area>/<name>.py`:
   - Subclass `Tool`; `name`, `description`, `params_model: ClassVar[type[ToolParams]]` (`extra="forbid"`, `frozen=True`, bounded `Field`s).
   - `__init__` takes only process-lifetime deps (`session_factory`, clients, `ApprovalTokenVerifier`). No `AsyncSession`, no ACL set.
   - `async def execute(self, *, ...) -> str`. Read `get_request_context()` here. Open DB with `async with self._session_factory()`.
   - Untrusted text through `SecuritySanitizer` before return.
2. Side-effecting send/post: **new** tool name, add to `GATED_TOOLS`, mixin `GatedMCPTool`, `approval_token` kwarg **not** in `params_model`, `_ensure_approved()` before the side effect. Pair with an ungated read tool if needed. HITL pause is `interrupt()` in `continuation.py`, not in the tool.
3. Register in `wiring/factories/tools.py` `register_tools()`.
4. Grant in `_build_default_agent_policies()` (`wiring/factories/agent_policies.py`) — treat as a permission change. Messaging stays behind `ENABLE_MESSAGING_TOOLS`.
5. If `ParserTool` type: also `core.constants.SUPPORTED_UPLOAD_CONTENT_TYPES`.
6. Tests: unit for execute + ACL/session; `registry/test_tool_registry.py` must see `params_model` match `execute()`. If gated, e2e HITL pattern in `tests/e2e/test_hitl_approval_flow.py`.

`$ARGUMENTS` should include tool name, side-effecting or not, and which agents may use it.
