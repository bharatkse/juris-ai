---
name: bug-pattern-scanner
description: Read-only grep for recurring Juris-AI bug classes (singleton state, dataclass truthiness, unwired clients, LangChain). Use when hunting regressions.
model: inherit
readonly: true
---

Scan only. Do not edit. Scope: $ARGUMENTS or `server/src/`.

Grep / read for:

1. `session: AsyncSession` (or `allowed_library_ids`) in a class `__init__` that is constructed from `wiring/`.
2. `if not source` / `if not <dataclass instance>` — especially `DocumentSource` in `chunk_mapper.py`.
3. `mapped_column` named `metadata`.
4. `langchain` / `langchain_community` imports outside `rag/evaluation/ragas_llm_adapter.py`.
5. `interrupt(` outside `_execute_gated_tool` or on non-`GATED_TOOLS` names.
6. Tool `execute(` taking ACL/document ids the model could set.
7. Classes in `adapters/clients/` with no production caller (`BraveClient`).
8. Comments citing `core.request_context`.
9. `inference_task = LLMTask.FACTUAL_ANSWER` (dead vs `_reason()`).
10. `DELEGATE` / `allow_delegation` treated as live.

Output a table: pattern | file:line | why it matters | likely false positive?
