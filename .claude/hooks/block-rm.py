#!/usr/bin/env python3
"""PreToolUse hook: deny Bash commands that actually invoke rm with recursive+force flags.

Tokenizes the command like a shell (quotes respected), splits it on &&, ||, ;, |,
&, parentheses and newlines, and only inspects the command word of each segment
after stripping wrappers (sudo, env, xargs, ...). Recurses into bash/sh -c
strings, eval, find -exec, and $(...)/backtick substitutions. So `git rm -rf`,
`grep "rm -rf"` and `echo "rm -rf /"` pass, while `sudo rm -rf` and
`bash -c "rm -rf x"` are denied.
"""

import json
import os
import re
import shlex
import sys

# Wrappers that run the command that follows them, and their options that take a value
WRAPPERS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "-T"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S"},
    "xargs": {
        "-I",
        "-n",
        "-P",
        "-d",
        "-a",
        "-E",
        "-L",
        "-s",
        "--delimiter",
        "--arg-file",
    },
    "nice": {"-n"},
    "ionice": {"-c", "-n", "-p"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "command": set(),
    "builtin": set(),
    "exec": set(),
    "nohup": set(),
    "time": set(),
    "stdbuf": set(),
}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
SEPARATOR_CHARS = set("();|&\n")
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MAX_DEPTH = 5


def is_rm_rf(args):
    recursive = force = False
    for arg in args:
        if arg == "--":
            break
        if arg == "--recursive":
            recursive = True
        elif arg == "--force":
            force = True
        elif arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
            recursive |= "r" in arg or "R" in arg
            force |= "f" in arg
    return recursive and force


def split_segments(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    segment = []
    for token in lexer:
        if token and set(token) <= SEPARATOR_CHARS:
            if segment:
                yield segment
            segment = []
        else:
            segment.append(token)
    if segment:
        yield segment


def strip_wrappers(words):
    i = 0
    while i < len(words):
        word = words[i]
        if ASSIGNMENT.match(word):
            i += 1
            continue
        name = os.path.basename(word)
        if name not in WRAPPERS:
            break
        # timeout's first positional arg is the duration, not the command
        takes_duration = name == "timeout"
        i += 1
        while i < len(words) and words[i].startswith("-"):
            i += 2 if words[i] in WRAPPERS[name] else 1
        if takes_duration and i < len(words):
            i += 1
    return words[i:]


def segment_is_dangerous(words, depth):
    words = strip_wrappers(words)
    if not words:
        return False
    name = os.path.basename(words[0])
    args = words[1:]

    if name == "rm":
        return is_rm_rf(args)
    if name in SHELLS:
        for i, arg in enumerate(args):
            if arg.startswith("-") and not arg.startswith("--") and "c" in arg:
                return i + 1 < len(args) and command_is_dangerous(
                    args[i + 1], depth + 1
                )
        return False
    if name == "eval":
        return command_is_dangerous(" ".join(args), depth + 1)
    if name == "find":
        for i, arg in enumerate(args):
            if arg in ("-exec", "-execdir", "-ok", "-okdir"):
                return segment_is_dangerous(args[i + 1 :], depth + 1)
    return False


def command_is_dangerous(command, depth=0):
    if depth > MAX_DEPTH:
        return True
    # Command substitutions run unquoted or inside double quotes, never inside
    # single quotes; scan the raw text since tokenizing splits `...` apart
    unquoted = re.sub(r"'[^']*'", "", command)
    for match in SUBSTITUTION.finditer(unquoted):
        if command_is_dangerous(match.group(1) or match.group(2), depth + 1):
            return True
    try:
        segments = list(split_segments(command))
    except ValueError:
        # Unbalanced quotes: fall back to a conservative substring check
        return re.search(r"\brm\s+-\S*[rR]", command) is not None
    return any(segment_is_dangerous(seg, depth) for seg in segments)


def deny(reason):
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def main():
    try:
        command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
        dangerous = command_is_dangerous(command)
    except Exception as exc:
        # Fail closed: a parser bug or malformed input must not let rm -rf through
        deny(f"block-rm hook failed ({type(exc).__name__}: {exc}) -- confirm manually")
        return
    if dangerous:
        deny(
            "rm with recursive+force flags blocked by hook -- confirm manually if intentional"
        )


if __name__ == "__main__":
    main()
