---
description: Run lint/mypy/unit/smoke/e2e and write the standard end-of-phase report
argument-hint: "[--only lint,mypy,unit,smoke,e2e] [--keep-baseline]"
allowed-tools: Bash(.claude/scripts/phase-checks.py:*), Bash(.claude/hooks/report-staged-changes.py --report), Bash(git status:*), Bash(git diff:*)
---

Write the end-of-phase report for the work done in this session.

1. Run `.claude/scripts/phase-checks.py $ARGUMENTS` from the repo root. It
   runs the checks, prints the checks table with deltas against the last
   run (`.git/claude-phase-baseline.json`) and lists changed files. Smoke
   and e2e need the dependency containers; if they fail to connect, say
   so, don't report it as a test failure. A failing check's log is in
   `.git/claude-phase-logs/<check>.log`: read it and name the failing
   tests.
2. Run `.claude/hooks/report-staged-changes.py --report` last, after every other
   command, so it reflects the final index state.

Then write the report in exactly this shape, and nothing before it:

## Phase report: <one-line name of the phase>

### Checks
The table from step 1, as printed. Below it, one line per failure or
negative delta explaining it (pre-existing, caused by this change, or
environment).

### What was actually wrong vs. assumed
| Assumed going in | Actually | Evidence | Consequence |
|---|---|---|---|

One row per assumption this phase proved wrong — from the prompt, the docs,
CLAUDE.md or an earlier report. Evidence is `file:line`, a command and its
output, or a test name. If nothing turned out different, write one row
saying so; don't invent findings.

### Changed files
The code and docs lists from step 1, each with a few words on what changed.
If the doc-sync line was printed, say for each listed doc whether it is
still accurate or was missed. Backlog docs (`docs/architecture-review.md`,
`docs/agentic-fix-plan.md`) keep their old statuses until a PR number
exists; don't list them as missing an update.

### Needs sign-off
Numbered list of decisions that are yours to make before this merges:
judgment calls made along the way, anything deferred, guessed seed data,
behaviour changes, anything destructive. Each with a recommendation. If
there are none, write "None."

### Git index — check before committing
The output of step 2, verbatim. Then: "Nothing is committed. Run
`git status` and `git diff --cached --stat` before committing; the index
has drifted before." If anything is staged that isn't part of this phase,
say which files, in bold.
