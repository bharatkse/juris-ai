# Pre-PR check

Extra scope: $ARGUMENTS

Run from repo root. Do not skip hooks or commit.

## Commands

```bash
git status
git diff
make lint
make lint-imports
make type-check
make test-unit
```

If the diff touches persistence: remind that `make alembic-revision` is generate-only; do not hand-edit `versions/`. If RAG/chunker: note smoke/eval are not in the default unit job. If HITL/tools: mention `make test-e2e TARGET=test_hitl_approval_flow.py` as optional follow-up (needs stack).

## Risk vs rules

Summarize the diff against `.cursor/rules/`:

- Layer imports / `wiring/`-only construction
- Auth: no LLM; `check_intent` + `check_action`; ACL sentinel
- Tools: singleton + ContextVar; `GATED_TOOLS` + `interrupt()` only on sends
- DB: no `metadata` column; `session_factory()` per op
- LangChain not introduced on the runtime path
- Docs that name changed symbols (`docs/server/architecture/api.md`, layer README/CLAUDE)

List test gaps and files that look staged accidentally. Do not `git add` (repo hook blocks it from the agent).
