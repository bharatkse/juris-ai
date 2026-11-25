# Gap analysis vs design docs

Focus: $ARGUMENTS (default: agentic + RAG + auth).

## Sources of truth (read, don't assume)

1. Tracked: `docs/server/architecture/overview.md`, `api.md`, `docs/server/observability.md`, `server/src/**/README.md`, `server/src/**/CLAUDE.md`, root `CLAUDE.md`.
2. Local-only if present (gitignored): `docs/architecture-review.md`, `docs/agentic-fix-plan.md`, `docs/roadmap.md`.
3. Code: `wiring/composition.py`, orchestrator, executor, continuation, hybrid retriever, authorization facade.

## Method

For each claim in the docs (a named component, endpoint, failover, gate, metric):

- **Implemented and wired** (cite symbol + factory).
- **Implemented, unwired** (cite file; grep shows no production caller).
- **Documented, missing**.
- **Code exists, docs wrong** (e.g. `docker/clients/README.md` “no client” vs `clients/web/`; `RetrieverTool` ACL docstring; `core.request_context`).

Skip flipping backlog statuses unless a PR number exists (repo convention).

## Output

Table: ID or claim | status | evidence | suggested next change. Keep IDs from the review (S6, K10, R9, …) when those files exist.
