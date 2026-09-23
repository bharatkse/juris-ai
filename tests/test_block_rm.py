"""Tests for the .claude/hooks/block-rm.py PreToolUse hook.

Run with: .venv/bin/pytest tests/test_block_rm.py
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "block-rm.py"

_spec = importlib.util.spec_from_file_location("block_rm", HOOK_PATH)
block_rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(block_rm)


def blocked(command):
    return block_rm.command_is_dangerous(command)


def run_hook(stdin_text, executable=None, env=None):
    args = [str(HOOK_PATH)] if executable is None else [executable, str(HOOK_PATH)]
    return subprocess.run(
        args, input=stdin_text, capture_output=True, text=True, env=env
    )


# --- plain rm -------------------------------------------------------------


def test_plain_rm_rf_is_blocked():
    assert blocked("rm -rf /tmp/foo")


def test_rm_fr_flag_order_is_blocked():
    assert blocked("rm -fr /tmp/foo")


def test_rm_separate_r_and_f_flags_are_blocked():
    assert blocked("rm -r -f /tmp/foo")


def test_rm_long_recursive_force_flags_are_blocked():
    assert blocked("rm --recursive --force /tmp/foo")


def test_rm_absolute_binary_path_is_blocked():
    assert blocked("/bin/rm -rf /tmp/foo")


def test_rm_without_flags_is_allowed():
    assert not blocked("rm file.txt")


def test_rm_recursive_only_is_allowed():
    assert not blocked("rm -r build")


def test_rm_force_only_is_allowed():
    assert not blocked("rm -f file.txt")


# --- wrapped forms --------------------------------------------------------


def test_sudo_rm_rf_is_blocked():
    assert blocked("sudo rm -rf /tmp/foo")


def test_sudo_with_user_option_rm_rf_is_blocked():
    assert blocked("sudo -u root rm -rf /tmp/foo")


def test_env_rm_rf_is_blocked():
    assert blocked("env FOO=1 rm -rf /tmp/foo")


def test_xargs_rm_rf_is_blocked():
    assert blocked("ls | xargs rm -rf")


def test_timeout_rm_rf_is_blocked():
    assert blocked("timeout 5 rm -rf /tmp/foo")


def test_rm_rf_after_and_chain_is_blocked():
    assert blocked("cd /tmp && rm -rf foo")


def test_rm_rf_on_second_line_is_blocked():
    assert blocked("ls\nrm -rf /tmp/foo")


# --- nested forms ---------------------------------------------------------


def test_bash_c_rm_rf_is_blocked():
    assert blocked('bash -c "rm -rf /tmp/foo"')


def test_eval_rm_rf_is_blocked():
    assert blocked('eval "rm -rf /tmp/foo"')


def test_find_exec_rm_rf_is_blocked():
    assert blocked(r"find . -name '*.pyc' -exec rm -rf {} \;")


def test_backtick_substitution_rm_rf_is_blocked():
    assert blocked("echo `rm -rf /tmp/foo`")


def test_dollar_paren_substitution_rm_rf_is_blocked():
    assert blocked("echo $(rm -rf /tmp/foo)")


def test_substitution_inside_double_quotes_is_blocked():
    # Double quotes do not stop command substitution from executing
    assert blocked('echo "$(rm -rf /tmp/foo)"')


# --- quoted/literal occurrences that are not rm calls ---------------------


def test_echo_of_quoted_rm_rf_is_allowed():
    assert not blocked('echo "rm -rf /"')


def test_grep_for_rm_rf_string_is_allowed():
    assert not blocked('grep "rm -rf" foo.txt')


def test_git_rm_rf_cached_is_allowed():
    assert not blocked("git rm -rf --cached somefile.py")


def test_docker_rm_f_is_allowed():
    assert not blocked("docker rm -f container")


def test_single_quoted_substitution_is_allowed():
    # Single quotes suppress substitution, so nothing executes
    assert not blocked("echo '$(rm -rf /tmp/foo)'")


def test_echo_of_quoted_bash_c_rm_rf_is_allowed():
    assert not blocked("echo 'bash -c \"rm -rf x\"'")


# --- known over-blocking edge case ----------------------------------------


def test_quoted_semicolon_next_to_rm_rf_is_blocked_intentionally():
    # Over-blocks on purpose: the tokenizer can't tell a quoted ";" from a real
    # separator, so the trailing words are treated as a new `rm -rf` command.
    # Blocking a harmless echo is the safe failure mode for this control.
    assert blocked('echo ";" rm -rf /tmp/foo')


# --- hook I/O contract and failure modes ----------------------------------


def test_hook_emits_deny_json_for_rm_rf():
    result = run_hook(
        json.dumps({"tool_input": {"command": "rm -rf /tmp/foo"}}), sys.executable
    )
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert result.returncode == 0


def test_hook_emits_nothing_for_safe_command():
    result = run_hook(json.dumps({"tool_input": {"command": "ls -la"}}), sys.executable)
    assert result.stdout == ""
    assert result.returncode == 0


def test_hook_fails_closed_on_malformed_input():
    result = run_hook("not json", sys.executable)
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "block-rm hook failed" in decision["permissionDecisionReason"]


def test_hook_fails_closed_on_parser_exception(monkeypatch, capsys):
    def explode(command, depth=0):
        raise RuntimeError("parser bug")

    monkeypatch.setattr(block_rm, "command_is_dangerous", explode)
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": "ls"}}))
    )
    block_rm.main()
    decision = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "RuntimeError" in decision["permissionDecisionReason"]


@pytest.mark.skipif(sys.platform == "win32", reason="relies on the POSIX shebang")
def test_hook_fails_open_when_python3_is_missing():
    # KNOWN GAP: with no python3 on PATH the shebang can't start the script, so
    # it exits 127 with no output. Claude Code treats that as a non-blocking hook
    # error and ALLOWS the command. The script can't catch this itself; closing
    # it would need a settings-level fallback (e.g. `... || exit 2`).
    empty_path_env = {"PATH": "/nonexistent", "HOME": os.environ.get("HOME", "/")}
    result = run_hook(
        json.dumps({"tool_input": {"command": "rm -rf /tmp/foo"}}), env=empty_path_env
    )
    assert result.returncode == 127
    assert result.stdout == ""
