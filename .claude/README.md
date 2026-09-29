# Claude Code project config

Shared, committed Claude Code configuration for this repo. Anyone running
Claude Code here gets these hooks and permissions automatically.

| File | Tracked | Purpose |
|---|---|---|
| `settings.json` | yes | Team hooks + permissions (this doc) |
| `settings.local.json` | no (gitignored) | Your machine-local overrides, e.g. extra `allow` rules |
| `hooks/` | yes | Hook scripts referenced by `settings.json` |
| `commands/phase-report.md` | yes | `/phase-report`: the standard end-of-phase report |
| `scripts/phase-checks.py` | yes | Runs the checks for `/phase-report` |
| `agents/docs-sync.md` | yes | Read-only subagent: doc claims a diff made stale |
| `agents/screen-recorder.md` | yes | Subagent: screenshots/videos of a UI change, only on request (`agents/README.md`) |
| `agents/README.md` | yes | Subagent index and `screen-recorder` request format |
| `captures/` | no (gitignored) | `screen-recorder` output, may include test-user credentials |

Requirements on your machine: `jq`, `python3` on `PATH`, and the repo-root
venv (`make poetry-install`) for ruff and the test run.

## Hooks

| Event | Matcher | Script | Effect |
|---|---|---|---|
| PreToolUse | `Bash` | `hooks/block-rm.py` | Denies `rm` with recursive + force flags |
| PreToolUse | `Bash` | `hooks/guard-git-index.py` | Denies `git add` in any form; asks for `git mv`, `git rm` (not `--cached`), `git stash pop/apply` |
| PreToolUse | `Edit\|MultiEdit\|Write` | `hooks/block-env-and-revision-edits.sh` | Blocks edits to `.env*` and `migrations/versions/` paths |
| PostToolUse | `Edit\|MultiEdit\|Write` | `hooks/ruff-fix-on-edit.sh` | ruff fix + format on edited `.py` files |
| UserPromptSubmit | — | `hooks/report-staged-changes.py --event user-prompt` | Reports staged-set changes made between turns (IDE, terminal) |
| Stop | — | `hooks/check-types-and-tests-on-stop.sh` | Runs `make type-check` + `make test-unit` when Claude finishes a turn |
| Stop | — | `hooks/report-staged-changes.py --event stop` | Reports staged-set changes made during the turn |

### block-rm.py — rm -rf guard
Denies any Bash command that actually runs `rm` with both a recursive and a
force flag, in any spelling: `-rf`, `-fr`, `-r -f`, `-Rf`,
`--recursive --force`. It tokenizes the command like a shell (quotes
respected), splits on `&&`, `||`, `;`, `|`, `&`, parentheses and newlines,
strips wrappers (`sudo`, `env`, `xargs`, `timeout`, `nice`, ...), and
recurses into `bash -c`/`sh -c`, `eval`, `find -exec` and `$(...)`/backtick
substitutions.

- Allowed: `git rm -rf --cached x`, `grep "rm -rf" f`, `echo "rm -rf /"`,
  `rm -r dir`, `rm -f file`, `docker rm -f c`.
- Denied: `rm -rf x`, `sudo rm -rf x`, `cd /tmp && rm -rf x`,
  `bash -c "rm -rf x"`, `ls | xargs rm -rf`, `echo $(rm -rf x)`.
- **Why**: irreversible deletes should be run by a human. If Claude needs
  one, it will say so and you run it yourself.
- Fails **closed** on malformed input or a parser exception (denies with
  the error in the reason).
- Known limits: a quoted `";"` next to a separate `rm -rf` is over-blocked
  (intentional, safe side). If `python3` is missing the script can't start
  and Claude Code treats that as a non-blocking error — commands are
  **allowed** (fail-open).

There is deliberately no `"if"` condition on this hook: `"if": "Bash(rm *)"`
was tried and let `sudo rm -rf` and `bash -c "rm -rf ..."` through
unchecked. The script filters for itself.

### guard-git-index.py — index side effects
The static `Bash(git add:*)` deny only matches commands that start with
that text, so `git -C server add x` got through, and `git mv`, `git rm`
and `git stash pop` stage or unstage files as a side effect. This hook
reuses `block-rm.py`'s tokenizer (separators, wrappers, `bash -c`, `eval`,
`$(...)`), skips git's global options (`-C`, `-c`, `--git-dir`, ...) and
decides on the subcommand:

- deny: `add` in any form.
- ask: `mv`; `rm` without `--cached`; `stash pop`, `stash apply`.
- Heredoc bodies are data: a quoted heredoc (`<<'EOF'`) is skipped entirely;
  an unquoted one keeps only its `$(...)`/backtick substitutions. Without
  this, a Python heredoc merely mentioning `` `git add` `` was denied.
- Fails towards a human: a parser exception returns `ask`.

`settings.json` also carries the literal forms as static rules (`ask`:
`git mv`, `git stash pop`, `git stash apply`; `deny`: `git -C * add *`) so
they show in `/permissions`; the hook is what enforces the rest.

### report-staged-changes.py — staged-set drift report
Snapshots the index (`git diff --cached --raw`: path, status, staged blob)
to `.git/claude-staged-snapshot` and reports what changed since the last
snapshot: newly staged, no longer staged, re-staged with different content.
On UserPromptSubmit the change happened between turns, i.e. outside the
session (IDE staging, which no pre-commit hook can see); the message goes
to you and into Claude's context. On Stop it happened during the turn.
Silent when nothing changed; each change is reported once.
`.claude/hooks/report-staged-changes.py --report` prints the full staged list plus
the delta (used at the end of `/phase-report`).

### block-env-and-revision-edits.sh — secrets and migrations
Blocks Edit/Write to any path containing `.env` or `migrations/versions/`
(exit 2; Claude sees the reason). **Why**: secrets must not be touched by
an agent, and Alembic revisions must be generated (`make alembic-revision
msg="..."`), not hand-written. `migrations/env.py` is deliberately
editable: new externally managed tables go in its
`_EXTERNALLY_MANAGED_TABLES`. Limit: only covers the edit tools — a Bash
redirect (`echo x > .env`) is not intercepted.

### ruff-fix-on-edit.sh — ruff on edit
After an edit to a `.py` file: `ruff check --fix`, then `ruff format`, then
a final `ruff check`. Remaining violations or a formatter failure exit 2 so
Claude fixes them in the same turn. Uses `$CLAUDE_PROJECT_DIR/.venv/bin/ruff`
explicitly (not `PATH`); if that's missing it reports a non-blocking error.

### check-types-and-tests-on-stop.sh — mypy + unit tests on Stop
Runs `make type-check` (~2s warm) and `make test-unit` (unit only, ~40s)
when Claude ends a turn. mypy runs here rather than after each edit so a
half-finished multi-file change doesn't fail mid-turn. Both always run, so
one retry can fix type errors and test failures together.
- **Skip when unchanged**: fingerprints the tree (HEAD + `git diff HEAD` +
  untracked non-ignored files). If it matches the last green run, tests are
  skipped — chat-only turns cost nothing. Changes to gitignored files
  (e.g. `.env`) don't count.
- **One retry, never a loop**: on failure it blocks the stop once with the
  mypy errors and/or failing tests as the reason. On the retry (`stop_hook_active=true`) the
  stop is always allowed and the failure is shown to you as a
  `systemMessage`.
- State lives in `.git/claude-last-green` and a log in
  `.git/claude-stop-hook.log` (one line per stop: `skipped` / `ran: passed`
  / `ran: failed`) — never shows up in `git status`.

There is deliberately no Notification hook. The former `notify.sh` emitted
an OSC 777 escape sequence, which does nothing in the VS Code extension (it
has its own attention prompts); CLI users should use Claude Code's built-in
notification setting (`/config`) instead.

## Permissions
`settings.json` denies `git add` (also as `git -C <dir> add`), `git commit`,
`git push`, `git reset` and `git merge` for Claude: staging, committing and
anything that rewrites or publishes history stays with a human. `git mv`,
`git stash pop` and `git stash apply` ask first (see guard-git-index.py),
as do `gh pr create` (it can push the branch itself) and `gh pr merge`.

`make db-query` is safe to auto-allow only because
`server/scripts/bash/db_query.sh` validates the SQL first: `BEGIN READ WRITE`
would otherwise reopen writes, and psql's `\!` runs a shell as root in the
Postgres container (both reproduced). See the script's header.
To let Claude commit on your machine only, add `allow` rules in
`.claude/settings.local.json`.

Allowed without a prompt: `grep`, `sed -n`, `git status/diff/log/show`,
`make lint`, `make lint-imports`, `make type-check`, `make test-unit/-smoke/-e2e/-integration/-root`,
`make -s floci-env`, `report-staged-changes.py --report`, `make db-query`,
`make alembic-current`, and read-only `gh` (`gh pr view/checks/list`,
`gh run view/list`). Known looseness: prefix
rules also match `sed -n -i ...` and `git diff --output=<file>`, which
write files; tighten if that ever matters.

## /phase-report and docs-sync
`/phase-report [--only lint,mypy,...] [--keep-baseline]` runs
`scripts/phase-checks.py` (lint, mypy, unit, smoke, e2e), which prints the
checks table with deltas against the previous run
(`.git/claude-phase-baseline.json`; logs in `.git/claude-phase-logs/`) and
the changed files, flagging the docs that must change with code if
`server/src` changed and they didn't. Claude then fills in the "actually
wrong vs. assumed" table and the sign-off list, and ends with
`report-staged-changes.py --report`.

The `docs-sync` subagent takes a diff or git range and returns doc claims it
made stale, with `file:line` evidence from the code. It's read-only, skips
the backlog docs unless given a PR number, and never suggests finding IDs
in the public design docs.

## Testing the hooks
`tests/test_block_rm.py` (repo-root `tests/`) covers `block-rm.py`: plain,
wrapped and nested forms, quoted non-calls, the intentional over-block, and
the fail-closed / fail-open paths.

```bash
make test-root                                  # all repo-root tests
make test-root TARGET=test_block_rm.py          # just the hook tests
```

`tests/test_guard_git_index.py` and `tests/test_staged_check.py` cover the
git-index hooks (the latter against throwaway repos).

The other hooks have no automated tests yet; check them by hand (edit a
`.py` file with a lint error, try writing `test.env`, end a turn and read
`.git/claude-stop-hook.log`).
