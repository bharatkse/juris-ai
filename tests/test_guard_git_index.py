"""Tests for the .claude/hooks/guard-git-index.py PreToolUse hook.

Run with: make test-root TARGET=test_guard_git_index.py
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "guard-git-index.py"
)

_spec = importlib.util.spec_from_file_location("guard_git_index", HOOK_PATH)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def decision(command):
    return guard.classify(command)[0]


@pytest.mark.parametrize(
    "command",
    [
        "git add x.py",
        "git -C server add x.py",
        "git -c core.autocrlf=false add .",
        "git --git-dir=.git add x",
        "cd server && git add -N foo.py",
        'bash -c "git add x"',
        "env GIT_TRACE=1 git add x",
    ],
)
def test_add_in_any_form_is_denied(command):
    assert decision(command) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "git mv a.py b.py",
        "git -C server mv a.py b.py",
        "git rm old.py",
        "git rm -r old_dir",
        "git stash pop",
        "git stash apply stash@{1}",
        "git -C server stash pop",
        "echo $(git stash pop)",
    ],
)
def test_index_side_effects_ask(command):
    assert decision(command) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git diff --cached --name-only",
        "git log --oneline -5",
        "git rm --cached secrets.txt",
        "git stash list",
        "git stash show -p",
        'grep -rn "git add" docs/',
        "echo 'git stash pop'",
        "rm file.txt",
    ],
)
def test_read_only_and_quoted_commands_pass(command):
    assert decision(command) is None


def test_deny_outranks_ask_in_one_command():
    assert decision("git mv a b && git add b") == "deny"


def run_hook(stdin_text):
    return subprocess.run(
        [str(HOOK_PATH)], input=stdin_text, capture_output=True, text=True
    )


def test_hook_emits_ask_json():
    result = run_hook(json.dumps({"tool_input": {"command": "git mv a b"}}))
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "ask"
    assert "git mv" in out["permissionDecisionReason"]


def test_hook_is_silent_for_harmless_commands():
    result = run_hook(json.dumps({"tool_input": {"command": "git status"}}))
    assert result.returncode == 0
    assert result.stdout == ""


def test_hook_asks_on_malformed_input():
    result = run_hook("not json")
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "ask"


def test_quoted_heredoc_body_is_data():
    command = "python3 - <<'EOF'\ns = 'run `git add` then git stash pop'\ngit add x\nEOF\necho done"
    assert decision(command) is None


def test_unquoted_heredoc_body_still_expands_substitutions():
    assert decision("cat <<EOF\nnote: git add x\nEOF") is None
    assert decision("cat <<EOF\n$(git stash pop)\nEOF") == "ask"


def test_command_after_heredoc_is_still_checked():
    assert decision("cat <<'EOF' > f\ntext\nEOF\ngit mv a b") == "ask"
