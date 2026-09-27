# Claude Code project config

Shared, committed Claude Code configuration for this repo. Anyone running
Claude Code here gets these hooks and permissions automatically.

| File | Tracked | Purpose |
|---|---|---|
| `settings.json` | yes | Team hooks + permissions (this doc) |
| `settings.local.json` | no (gitignored) | Your machine-local overrides, e.g. extra `allow` rules |
| `hooks/` | yes | Hook scripts referenced by `settings.json` |

Requirements on your machine: `jq`, `python3` on `PATH`, and the repo-root
venv (`make poetry-install`) for ruff and the test run.

## Hooks

| Event | Matcher | Script | Effect |
|---|---|---|---|
| PreToolUse | `Bash` | `hooks/block-rm.py` | Denies `rm` with recursive + force flags |
| PreToolUse | `Edit\|MultiEdit\|Write` | `hooks/block-sensitive-edit.sh` | Blocks edits to `.env*` and `migrations/` paths |
| PostToolUse | `Edit\|MultiEdit\|Write` | `hooks/lint-fix.sh` | ruff fix + format on edited `.py` files |
| Stop | — | `hooks/run-tests.sh` | Runs `make test-unit` when Claude finishes a turn |
| Notification | — | `hooks/notify.sh` | Terminal notification when Claude needs attention |

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

### block-sensitive-edit.sh — secrets and migrations
Blocks Edit/Write to any path containing `.env` or `migrations/` (exit 2;
Claude sees the reason). **Why**: secrets must not be touched by an agent,
and Alembic revisions must be generated (`make alembic-revision
msg="..."`), not hand-written. Limit: only covers the edit tools — a Bash
redirect (`echo x > .env`) is not intercepted.

### lint-fix.sh — ruff on edit
After an edit to a `.py` file: `ruff check --fix`, then `ruff format`, then
a final `ruff check`. Remaining violations or a formatter failure exit 2 so
Claude fixes them in the same turn. Uses `$CLAUDE_PROJECT_DIR/.venv/bin/ruff`
explicitly (not `PATH`); if that's missing it reports a non-blocking error.

### run-tests.sh — unit tests on Stop
Runs `make test-unit` (unit only, ~25s) when Claude ends a turn.
- **Skip when unchanged**: fingerprints the tree (HEAD + `git diff HEAD` +
  untracked non-ignored files). If it matches the last green run, tests are
  skipped — chat-only turns cost nothing. Changes to gitignored files
  (e.g. `.env`) don't count.
- **One retry, never a loop**: on failure it blocks the stop once with the
  failing tests as the reason. On the retry (`stop_hook_active=true`) the
  stop is always allowed and the failure is shown to you as a
  `systemMessage`.
- State lives in `.git/claude-last-green` and a log in
  `.git/claude-stop-hook.log` (one line per stop: `skipped` / `ran: passed`
  / `ran: failed`) — never shows up in `git status`.

### notify.sh
Emits an OSC 777 terminal notification with the event's message. Needs a
terminal that supports OSC 777; otherwise it's a no-op.

## Permissions
`settings.json` denies `git add`, `git commit`, `git push`, `git reset` and
`git merge` for Claude: staging, committing and anything that rewrites or
publishes history stays with a human. To let Claude commit on your machine
only, add `allow` rules in `.claude/settings.local.json`.

## Testing the hooks
`tests/test_block_rm.py` (repo-root `tests/`) covers `block-rm.py`: plain,
wrapped and nested forms, quoted non-calls, the intentional over-block, and
the fail-closed / fail-open paths.

```bash
make test-root                                  # all repo-root tests
make test-root TARGET=test_block_rm.py          # just the hook tests
```

The other hooks have no automated tests yet; check them by hand (edit a
`.py` file with a lint error, try writing `test.env`, end a turn and read
`.git/claude-stop-hook.log`).
