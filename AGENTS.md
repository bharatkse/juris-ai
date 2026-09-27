# Agent guide (Juris-AI)

Cursor project rules live in [`.cursor/rules/`](.cursor/rules/) (`project-overview.mdc` is always on). Commands: [`.cursor/commands/`](.cursor/commands/). Subagents: [`.cursor/agents/`](.cursor/agents/). Skills: [`.cursor/skills/`](.cursor/skills/).

Layer maps, make targets, and do-nots: root `CLAUDE.md` and `server/src/<layer>/CLAUDE.md`. Python package: `server/`. Do not invent a second composition root, a LangChain runtime path, or a `dry_run()` tool API — HITL is `interrupt()` on `GATED_TOOLS` only.

Before a PR: `.cursor/commands/pre-pr.md`.
