#!/usr/bin/env python3
"""Report changes to the git index (staged set) since the last snapshot.

Staging has drifted before commits more than once: an IDE staged files in
parallel with a session, and `git mv`/`git rm`/`git stash pop` stage as a side
effect. A pre-commit hook can't see IDE staging, so this compares the index
against a snapshot at every turn boundary instead:

  --event user-prompt   UserPromptSubmit hook: changes since the end of the
                        last turn were made outside this session (IDE,
                        terminal). Shown to the user and added to Claude's
                        context.
  --event stop          Stop hook: changes made during this turn.
  --report              Plain text for /phase-report or a manual check: the
                        full staged list plus the delta. Exit 0 either way.

Entries are compared by path, status and staged blob id, so re-staging new
content under the same path counts as a change. The snapshot lives under
.git/ (claude-staged-snapshot), so it never shows up in git status. Every
mode rewrites it, so each change is reported once.
"""

import argparse
import json
import os
import subprocess
import sys

MAX_LISTED = 20


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def staged_entries():
    """{path: "STATUS blob"} for everything that differs between HEAD and the index."""
    try:
        out = git("diff", "--cached", "--raw", "--no-renames", "--no-abbrev", "-z")
    except subprocess.CalledProcessError:
        # No HEAD yet (fresh repo): everything in the index is staged
        out = git(
            "diff",
            "--cached",
            "--raw",
            "--no-renames",
            "--no-abbrev",
            "-z",
            git("hash-object", "-t", "tree", "/dev/null").strip(),
        )
    entries = {}
    fields = out.split("\0")
    for meta, path in zip(fields[0::2], fields[1::2]):
        if not meta.startswith(":"):
            continue
        _, _, _, new_blob, status = meta[1:].split(" ")
        entries[path] = f"{status} {new_blob}"
    return entries


def load_snapshot(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_snapshot(path, entries):
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(entries, f, sort_keys=True)
    os.replace(tmp, path)


def listing(label, paths):
    shown = sorted(paths)[:MAX_LISTED]
    more = len(paths) - len(shown)
    lines = [f"{label} ({len(paths)}):"] + [f"  {p}" for p in shown]
    if more > 0:
        lines.append(f"  ... and {more} more")
    return lines


def describe_delta(before, after):
    newly = [p for p in after if p not in before]
    gone = [p for p in before if p not in after]
    changed = [p for p in after if p in before and before[p] != after[p]]
    lines = []
    if newly:
        lines += listing("newly staged", newly)
    if gone:
        lines += listing("no longer staged", gone)
    if changed:
        lines += listing("re-staged with different content or status", changed)
    return lines


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--event", choices=["user-prompt", "stop"])
    group.add_argument("--report", action="store_true")
    opts = parser.parse_args()

    if opts.event:
        # Hooks get JSON on stdin; nothing in it is needed here
        sys.stdin.read()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        os.chdir(project_dir)

    try:
        snapshot_path = git("rev-parse", "--git-path", "claude-staged-snapshot").strip()
        current = staged_entries()
    except (OSError, subprocess.CalledProcessError) as exc:
        if opts.report:
            print(f"report-staged-changes: could not read the git index ({exc})")
        return 0

    previous = load_snapshot(snapshot_path)
    save_snapshot(snapshot_path, current)

    if opts.report:
        if current:
            print("\n".join(listing("Staged now", current)))
        else:
            print("Index clean: nothing staged.")
        if previous is None:
            print("No earlier snapshot to compare against; baseline recorded.")
        else:
            delta = describe_delta(previous, current)
            print(
                "\n".join(["Changed since last snapshot:"] + delta)
                if delta
                else "Unchanged since last snapshot."
            )
        return 0

    if previous is None:
        if not current:
            return 0
        header = "git index baseline recorded; files already staged"
        body = listing("staged", current)
    else:
        body = describe_delta(previous, current)
        if not body:
            return 0
        header = (
            "git index changed since the end of the last turn (outside this "
            "session: IDE or terminal)"
            if opts.event == "user-prompt"
            else "git index changed during this turn"
        )
    message = f"{header}. Check before committing:\n" + "\n".join(body)

    output = {"systemMessage": message}
    if opts.event == "user-prompt":
        output["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": message,
        }
    json.dump(output, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
