"""Tests for the .claude/hooks/report-staged-changes.py staged-set hook.

Each test runs the script against a throwaway git repo.
Run with: make test-root TARGET=test_staged_check.py
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "hooks"
    / "report-staged-changes.py"
)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("a\n")
    git(tmp_path, "add", "a.py")
    git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def run(repo, *args):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    return subprocess.run(
        [str(HOOK_PATH), *args], input="{}", capture_output=True, text=True, env=env
    )


def hook(repo, event):
    result = run(repo, "--event", event)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout else None


def test_clean_index_first_run_is_silent(repo):
    assert hook(repo, "stop") is None


def test_first_run_with_staged_files_reports_baseline(repo):
    (repo / "b.py").write_text("b\n")
    git(repo, "add", "b.py")
    out = hook(repo, "stop")
    assert "baseline" in out["systemMessage"]
    assert "b.py" in out["systemMessage"]


def test_unchanged_index_is_silent(repo):
    hook(repo, "stop")
    assert hook(repo, "user-prompt") is None


def test_ide_staging_between_turns_is_reported_once(repo):
    hook(repo, "stop")
    (repo / "b.py").write_text("b\n")
    git(repo, "add", "b.py")  # the "IDE" stages while Claude is idle
    out = hook(repo, "user-prompt")
    assert "outside this session" in out["systemMessage"]
    assert "newly staged (1)" in out["systemMessage"]
    assert "b.py" in out["hookSpecificOutput"]["additionalContext"]
    assert hook(repo, "user-prompt") is None


def test_unstaging_and_restaging_are_reported(repo):
    (repo / "a.py").write_text("a2\n")
    (repo / "b.py").write_text("b\n")
    git(repo, "add", "a.py", "b.py")
    hook(repo, "stop")
    (repo / "a.py").write_text("a3\n")
    git(repo, "add", "a.py")  # same path, new content
    git(repo, "restore", "--staged", "b.py")
    msg = hook(repo, "stop")["systemMessage"]
    assert "during this turn" in msg
    assert "no longer staged (1)" in msg and "b.py" in msg
    assert "re-staged with different content or status (1)" in msg


def test_git_mv_side_effect_is_reported(repo):
    hook(repo, "stop")
    git(repo, "mv", "a.py", "c.py")
    msg = hook(repo, "stop")["systemMessage"]
    assert "a.py" in msg and "c.py" in msg


def test_report_mode(repo):
    first = run(repo, "--report").stdout
    assert "Index clean" in first and "baseline recorded" in first
    (repo / "b.py").write_text("b\n")
    git(repo, "add", "b.py")
    second = run(repo, "--report").stdout
    assert "Staged now (1)" in second and "newly staged (1)" in second


def test_snapshot_lives_under_git_dir(repo):
    hook(repo, "stop")
    assert (repo / ".git" / "claude-staged-snapshot").exists()
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
    ).stdout
    assert status == ""


def test_outside_a_repo_is_silent(tmp_path):
    assert hook(tmp_path, "user-prompt") is None
