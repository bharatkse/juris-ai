---
name: langgraph-approval-gates
description: Adds a LangGraph interrupt() HITL gate for Juris-AI gated tools (email_send/slack_post). Use when adding side-effecting tools, approval pauses, or resume/replay-safe tool calls.
---

# LangGraph approval gates

There is no `dry_run()` API. The gate is: validate → `interrupt(plain dict)` → human decides on **that payload** → execute once outside the replayed node.

## When to pause

Only members of `GATED_TOOLS` in `server/src/agentic/tools/constants.py` (today `email_send`, `slack_post`). Read tools stay ungated. Approval policy: `ApprovalLifecyclePolicy` requires `ActionTypeEnum.SEND`.

## Implementation checklist

1. **Tool**: separate send tool; mixin `GatedMCPTool`; `approval_token` not in `params_model`; `_ensure_approved()` before the MCP side effect (`tools/messaging/base.py`).
2. **Decision path**: `agents/runtime/execution.py` treats these names as SEND. `AgentContinuationService._execute_gated_tool()` (`continuation.py`) must:
   - `check_parameters()` first (invalid draft is fed back, no pause).
   - Call `interrupt({execution_id, thread_id, conversation_event_id, agent_id, action_type, actor_type, tool_name, parameters, reason})` — **dict only** (msgpack checkpointer).
   - On resume, `decision == "approved"` → `ToolResult.from_dict(resume_payload["tool_result"])`; else failed `ToolResult`.
3. **Do not execute the send inside the node on resume.** `HitlResumeService` → `Executor.run_approved_tool()` runs it, persists on `AgentAction`, then `graph.ainvoke(Command(resume=...))`.
4. **Replay**: LangGraph replays the **whole node**. Ungated `execute()` in the same turn must go through `_execute_tool()`’s `@task` (`langgraph.func.task`) so replay returns the checkpointed result. Closures over `ToolExecutionService` are OK; declared task args must be serializable.
5. **Claim once**: `AgentActionRepository.claim()`; `ApprovalRepository.save_decision()` conditional on `waiting` (409 on concurrent decide). Re-check user permission before a **fresh** send, not when reusing a stored result.

## Do not

- Pass dataclasses into `interrupt()`.
- Wrap `_delegate()` the same way without reading the A9/K13 notes (delegation denied in production).
- Pause on retriever/web_research/library_lookup.

## Tests

`make test-unit TARGET=agentic/agents/runtime` and `make test-e2e TARGET=test_hitl_approval_flow.py` (real Postgres checkpointer).
