"""Tests for .github/scripts/rc-tag.sh (the rc-tag job in ci-server.yml).

The script runs against a stub `gh` (tests/gh_stub.py) that fails the way the
real gh does: exit 1, the raw error JSON on stdout and
``gh: <message> (HTTP <status>)`` on stderr -- the shape that made the old
inline check read a 404 as an existing tag.

Run with: .venv/bin/pytest tests/test_rc_tag.py
"""

import pytest
from gh_stub import API_ERRORS, REPO_ROOT, http_error, not_found, run_with_stub_gh

SCRIPT = REPO_ROOT / ".github" / "scripts" / "rc-tag.sh"

REPO = "bharatkse/juris-ai"
RC = "0.2.0-rc.1"
COMMIT = "1111111111111111111111111111111111111111"
OTHER_COMMIT = "2222222222222222222222222222222222222222"
TAG_OBJECT = "3333333333333333333333333333333333333333"
NEW_TAG_OBJECT = "4444444444444444444444444444444444444444"

REF_PATH = f"repos/{REPO}/git/ref/tags/v{RC}"


def run_rc_tag(tmp_path, routes):
    return run_with_stub_gh(
        tmp_path,
        [SCRIPT],
        routes,
        env={
            "REPO": REPO,
            "RC": RC,
            "IMAGE": "ghcr.io/bharatkse/juris-ai",
            "DIGEST": "sha256:abc",
            "GITHUB_SHA": COMMIT,
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        },
    )


def created_tag(calls):
    return any(call[1] == f"repos/{REPO}/git/refs" for call in calls)


CREATE_ROUTES = {
    f"POST repos/{REPO}/git/tags": {"stdout": NEW_TAG_OBJECT},
    f"POST repos/{REPO}/git/refs": {"stdout": "{}"},
}


def test_missing_tag_is_created_not_reported_as_existing(tmp_path):
    """The reported bug: a 404 must mean "no tag" and let creation proceed."""
    result, calls = run_rc_tag(
        tmp_path, {f"GET {REF_PATH}": not_found(), **CREATE_ROUTES}
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "already exists" not in result.stdout + result.stderr
    assert f"Tagged {COMMIT} as v{RC}" in result.stdout

    create_tag, create_ref = calls[1], calls[2]
    assert create_tag[1] == f"repos/{REPO}/git/tags"
    assert f"tag=v{RC}" in create_tag and f"object={COMMIT}" in create_tag
    assert create_ref[1] == f"repos/{REPO}/git/refs"
    assert (
        f"ref=refs/tags/v{RC}" in create_ref and f"sha={NEW_TAG_OBJECT}" in create_ref
    )


@pytest.mark.parametrize("status, message", API_ERRORS)
def test_other_lookup_errors_fail_without_creating_a_tag(tmp_path, status, message):
    """A real API error is neither "tag exists" nor "no tag": it fails the step."""
    result, calls = run_rc_tag(
        tmp_path,
        {f"GET {REF_PATH}": http_error(status, message), **CREATE_ROUTES},
    )

    assert result.returncode != 0
    assert f"(HTTP {status})" in result.stderr
    assert "already exists" not in result.stdout + result.stderr
    assert not created_tag(calls)


def test_annotated_tag_on_this_commit_is_kept(tmp_path):
    result, calls = run_rc_tag(
        tmp_path,
        {
            f"GET {REF_PATH}": {"stdout": f"tag {TAG_OBJECT}"},
            f"GET repos/{REPO}/git/tags/{TAG_OBJECT}": {"stdout": COMMIT},
        },
    )

    assert result.returncode == 0, result.stderr
    assert "keeping it" in result.stdout
    assert not created_tag(calls)


def test_annotated_tag_on_another_commit_fails(tmp_path):
    result, calls = run_rc_tag(
        tmp_path,
        {
            f"GET {REF_PATH}": {"stdout": f"tag {TAG_OBJECT}"},
            f"GET repos/{REPO}/git/tags/{TAG_OBJECT}": {"stdout": OTHER_COMMIT},
        },
    )

    assert result.returncode == 1
    assert f"v{RC} already exists on {OTHER_COMMIT}, not on {COMMIT}" in result.stdout
    assert not created_tag(calls)


def test_lightweight_tag_on_this_commit_is_kept(tmp_path):
    """
    A lightweight tag's ref points at the commit itself. The old check tried
    to peel it as a tag object; that 404's error JSON plus the fallback SHA
    never equalled the commit, so a re-run failed with a false mismatch.
    """
    result, calls = run_rc_tag(
        tmp_path, {f"GET {REF_PATH}": {"stdout": f"commit {COMMIT}"}}
    )

    assert result.returncode == 0, result.stderr
    assert "keeping it" in result.stdout
    assert [call[1] for call in calls] == [REF_PATH]
