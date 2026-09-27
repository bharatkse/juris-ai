"""Tests for .github/scripts/sync-release-pr.sh's CHANGELOG.md lookup.

develop may not have a CHANGELOG.md yet: a 404 must compare as an empty file.
Any other API failure must fail the step, not pass for "no changelog". Runs
against the stub `gh` in tests/gh_stub.py, which fails the way the real gh
does (exit 1, error JSON on stdout, ``gh: <message> (HTTP <status>)`` on
stderr).

Run with: .venv/bin/pytest tests/test_sync_release_pr.py
"""

import base64

import pytest
from gh_stub import API_ERRORS, REPO_ROOT, http_error, not_found, run_with_stub_gh

SCRIPT = REPO_ROOT / ".github" / "scripts" / "sync-release-pr.sh"

REPO = "bharatkse/juris-ai"
VERSION = "0.2.0"
DEVELOP_SHA = "5555555555555555555555555555555555555555"
BRANCH = f"release/sync-v{VERSION}"

CHANGELOG_PATH = f"repos/{REPO}/contents/CHANGELOG.md?ref={DEVELOP_SHA}"
CHANGELOG = "# CHANGELOG\n\n## v0.2.0\n\n- First release.\n"


def github_content(text):
    """Base64 the way the contents API returns it (wrapped lines)."""
    return base64.encodebytes(text.encode()).decode()


def routes(changelog_response):
    return {
        "PR list": {"stdout": ""},
        f"GET repos/{REPO}/git/ref/heads/develop": {"stdout": DEVELOP_SHA},
        f"GET repos/{REPO}/contents/server/pyproject.toml?ref={DEVELOP_SHA}": {
            "stdout": github_content(
                f'[project]\nname = "juris-ai"\nversion = "{VERSION}"\n'
            )
        },
        f"GET {CHANGELOG_PATH}": changelog_response,
        # Step 3: create the sync branch, commit, open the PR.
        f"GET repos/{REPO}/git/ref/heads/{BRANCH}": not_found(),
        f"POST repos/{REPO}/git/refs": {"stdout": "{}"},
        "GRAPHQL": {"stdout": "https://github.com/bharatkse/juris-ai/commit/abc"},
        "PR create": {"stdout": "https://github.com/bharatkse/juris-ai/pull/99"},
    }


def run_sync(tmp_path, changelog_response, local_changelog):
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text(local_changelog)

    return run_with_stub_gh(
        tmp_path,
        [SCRIPT, VERSION, changelog_file, "https://example.test/run/1"],
        routes(changelog_response),
        env={"GH_REPO": REPO, "GH_TOKEN": "stub"},
        cwd=REPO_ROOT,
    )


def opened_pr(calls):
    return any(call[:2] == ["pr", "create"] for call in calls)


def touched_branch(calls):
    """Step 3 started: the sync branch was looked up, created or reset."""
    return any(call[0] == "api" and BRANCH in " ".join(call) for call in calls)


def test_missing_changelog_compares_as_empty(tmp_path):
    """404 on develop + an empty release changelog: nothing to sync."""
    result, calls = run_sync(tmp_path, not_found(), local_changelog="")

    assert result.returncode == 0, result.stderr
    assert "no sync PR needed" in result.stdout
    assert not touched_branch(calls)


def test_missing_changelog_proceeds_to_open_the_sync_pr(tmp_path):
    """404 on develop + a real release changelog: the sync PR is opened."""
    result, calls = run_sync(tmp_path, not_found(), local_changelog=CHANGELOG)

    assert result.returncode == 0, result.stderr
    assert "Could not read CHANGELOG.md" not in result.stderr
    assert opened_pr(calls)


def test_existing_changelog_is_decoded_and_compared(tmp_path):
    result, calls = run_sync(
        tmp_path, {"stdout": github_content(CHANGELOG)}, local_changelog=CHANGELOG
    )

    assert result.returncode == 0, result.stderr
    assert "no sync PR needed" in result.stdout
    assert not touched_branch(calls)


@pytest.mark.parametrize("status, message", API_ERRORS)
@pytest.mark.parametrize("local_changelog", ["", CHANGELOG])
def test_other_lookup_errors_fail_instead_of_meaning_no_changelog(
    tmp_path, status, message, local_changelog
):
    """
    A real API error fails the step with gh's message. It must not pass for
    "no changelog": with an empty release changelog that would wrongly skip
    the sync, and with a real one it would open a PR on a guess.
    """
    result, calls = run_sync(
        tmp_path, http_error(status, message), local_changelog=local_changelog
    )

    assert result.returncode != 0
    assert "Could not read CHANGELOG.md on develop" in result.stderr
    assert f"(HTTP {status})" in result.stderr
    assert "no sync PR needed" not in result.stdout
    assert not touched_branch(calls)
    assert not opened_pr(calls)
