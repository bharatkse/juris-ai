"""
Build the GraphQL createCommitOnBranch request for the release sync PR.

Prints JSON for `gh api graphql --input -`. The commit:
  - sets [project].version in develop's own server/pyproject.toml (only that
    line; develop may have changed the rest since the release was cut)
  - replaces CHANGELOG.md with the one semantic-release regenerated

Commits made through this API with the workflow token are signed by GitHub,
which develop's signed-commit ruleset requires. Called by the `release` job
in .github/workflows/ci-server.yml; runnable locally (no network).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import tomllib
from pathlib import Path

MUTATION = """
mutation ($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) {
    commit { url }
  }
}
"""

# [project].version is the first top-level `version = "..."` line; the
# inline-table dependency versions are never at the start of a line.
VERSION_LINE = re.compile(r'^version = "[^"]*"$', re.MULTILINE)


def set_project_version(pyproject: str, version: str) -> str:
    updated, count = VERSION_LINE.subn(f'version = "{version}"', pyproject, count=1)

    if count != 1:
        raise SystemExit("no top-level `version = ...` line in pyproject.toml")

    actual = tomllib.loads(updated)["project"]["version"]
    if actual != version:
        raise SystemExit(f"set project.version to {actual!r}, expected {version!r}")

    return updated


def encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--branch", required=True, help="sync branch name")
    parser.add_argument("--head", required=True, help="expected head oid (develop sha)")
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--pyproject", required=True, type=Path, help="develop's pyproject.toml"
    )
    parser.add_argument("--changelog", required=True, type=Path)
    args = parser.parse_args()

    pyproject = set_project_version(
        args.pyproject.read_text(encoding="utf-8"), args.version
    )

    payload = {
        "query": MUTATION,
        "variables": {
            "input": {
                "branch": {
                    "repositoryNameWithOwner": args.repo,
                    "branchName": args.branch,
                },
                "message": {
                    "headline": f"chore(release): sync v{args.version} to develop"
                },
                "expectedHeadOid": args.head,
                "fileChanges": {
                    "additions": [
                        {
                            "path": "server/pyproject.toml",
                            "contents": encode(pyproject),
                        },
                        {
                            "path": "CHANGELOG.md",
                            "contents": encode(
                                args.changelog.read_text(encoding="utf-8")
                            ),
                        },
                    ]
                },
            }
        },
    }

    json.dump(payload, sys.stdout)


if __name__ == "__main__":
    main()
