#!/usr/bin/env python3
"""PreToolUse hook: gate Bash commands that change the git index behind a human.

The static rules in settings.json only match a command that starts with the
literal text: `Bash(git add:*)` misses `git -C server add x`, and `git rm`
without `--cached` can't be expressed as a prefix at all. This hook reuses
block-rm.py's shell tokenizer (quotes, separators, wrappers, `bash -c`,
`eval`, `$(...)`) and inspects each git invocation after its global options:

- deny: `add` in any spelling (`git -C dir add`, `git -c k=v add`, ...)
- ask:  `mv`, `rm` without `--cached`, `stash pop`, `stash apply`

All of these stage or unstage files as a side effect; together with IDE-side
staging they are how the index drifted before commits.
"""

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "block_rm", Path(__file__).resolve().parent / "block-rm.py"
)
block_rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(block_rm)

# git global options that take a separate value
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
SEVERITY = {None: 0, "ask": 1, "deny": 2}
MAX_DEPTH = block_rm.MAX_DEPTH


def git_subcommand(args):
    """Return (subcommand, its args) after skipping git's global options."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_OPTS_WITH_VALUE else 1
    if i >= len(args):
        return None, []
    return args[i], args[i + 1 :]


def classify_git(args):
    sub, rest = git_subcommand(args)
    if sub == "add":
        return (
            "deny",
            "git add (any form, incl. git -C <dir> add) is reserved for a human",
        )
    if sub == "mv":
        return "ask", "git mv stages the rename as a side effect"
    if sub == "rm" and "--cached" not in rest:
        return "ask", "git rm without --cached stages the deletion as a side effect"
    if sub == "stash" and rest and rest[0] in ("pop", "apply"):
        return "ask", f"git stash {rest[0]} can restore or conflict staged state"
    return None, None


def worst(a, b):
    return a if SEVERITY[a[0]] >= SEVERITY[b[0]] else b


def classify_segment(words, depth):
    words = block_rm.strip_wrappers(words)
    if not words:
        return None, None
    name = os.path.basename(words[0])
    args = words[1:]
    if name == "git":
        return classify_git(args)
    if name in block_rm.SHELLS:
        for i, arg in enumerate(args):
            if arg.startswith("-") and not arg.startswith("--") and "c" in arg:
                if i + 1 < len(args):
                    return classify(args[i + 1], depth + 1)
                return None, None
        return None, None
    if name == "eval":
        return classify(" ".join(args), depth + 1)
    if name == "find":
        for i, arg in enumerate(args):
            if arg in ("-exec", "-execdir", "-ok", "-okdir"):
                return classify_segment(args[i + 1 :], depth + 1)
    return None, None


HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)\\?([A-Za-z_][A-Za-z0-9_]*)\2")


def strip_heredocs(command):
    """Drop heredoc bodies: they are data, never run as commands.

    A quoted delimiter (<<'EOF', <<"EOF", <<\\EOF) expands nothing, so the body
    goes entirely; an unquoted one still expands $(...)/backticks, so only
    those substitutions are kept.
    """
    lines = command.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for match in HEREDOC.finditer(line):
            dash, quote, word = match.groups()
            quoted = bool(quote) or line[match.start() :].lstrip(
                "<-"
            ).lstrip().startswith("\\")
            body = []
            while i < len(lines):
                end = lines[i].lstrip("\t") if dash else lines[i]
                i += 1
                if end == word:
                    break
                body.append(lines[i - 1])
            if not quoted:
                out += [
                    m.group(0) for m in block_rm.SUBSTITUTION.finditer("\n".join(body))
                ]
    return "\n".join(out)


def classify(command, depth=0):
    if depth > MAX_DEPTH:
        return "ask", "command nesting too deep to inspect"
    command = strip_heredocs(command)
    result = (None, None)
    unquoted = re.sub(r"'[^']*'", "", command)
    for match in block_rm.SUBSTITUTION.finditer(unquoted):
        result = worst(result, classify(match.group(1) or match.group(2), depth + 1))
    try:
        segments = list(block_rm.split_segments(command))
    except ValueError:
        if re.search(r"\bgit\b.*\b(add|mv|rm|stash)\b", command):
            return (
                "ask",
                "unparsable command mentions an index-changing git subcommand",
            )
        return result
    for seg in segments:
        result = worst(result, classify_segment(seg, depth))
    return result


def emit(decision, reason):
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": f"{reason} -- guard-git-index hook",
            }
        },
        sys.stdout,
    )


def main():
    try:
        command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
        decision, reason = classify(command)
    except Exception as exc:
        # Fail towards a human: a parser bug must not let staging through silently
        emit("ask", f"guard-git-index failed ({type(exc).__name__}: {exc})")
        return
    if decision:
        emit(decision, reason)


if __name__ == "__main__":
    main()
