# Juris-AI Architecture Review Rules

## Agentic Architecture

The following boundaries must be respected:

1. Orchestrator is responsible for planning only.
2. Executor is responsible for execution only.
3. Agents are responsible for reasoning only.
4. Tools are responsible for external actions only.
5. ExecutionPlan and ExecutionState must remain separate.
6. LangGraph is the execution runtime/topology layer.
7. Executor owns execution memory, execution state, and collaboration bus.
8. Agent-to-agent communication must go through the Collaboration Bus.
9. Agents must not directly bypass the Executor for tool execution.

## HITL

1. Normal chat must not enter the approval workflow.
2. Action workflows persist ActionRequest/action state.
3. READ/ANALYZE/GENERATE actions can execute automatically.
4. UPDATE/DELETE/SEND/SUBMIT/EXTERNAL actions require approval.

## Authorization

Authorization follows:

User Request
    ↓
Capability Analysis
    ↓
Application Permission
    ↓
Planner
    ↓
ExecutionPlan
    ↓
ActionRequestDTO
    ↓
Approval Policy

Authorization must not be bypassed by directly executing an action.

## RAG

1. Retrieval must remain provider/model agnostic.
2. Embeddings are stored separately from DocumentChunk.
3. Retrieval should use the configured embedding provider.
4. Vector search must not hard-code an LLM provider.
5. Reranking must remain separate from initial retrieval.

## General Backend Rules

1. Do not introduce blocking operations into async code without justification.
2. Database transactions must be explicit around multi-step state changes.
3. External calls require appropriate timeout/error handling.
4. Do not expose secrets in logs or API responses.
5. New behavior should have appropriate tests.
6. Avoid unnecessary architectural coupling.
