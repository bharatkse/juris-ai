#!/usr/bin/env bash
# Open (or finish opening) the PR that syncs a release's version and
# CHANGELOG.md back to develop. Safe to re-run: every step checks what a
# previous attempt already did.
#
# Usage: sync-release-pr.sh <version> <changelog> <run-url>
# Needs GH_TOKEN and GH_REPO (owner/name); run from the repo root.
#
#   1. A sync PR for this version is already open or merged -> done.
#   2. develop already has this version and this CHANGELOG.md -> done.
#   3. Point release/sync-vX.Y.Z at CURRENT develop (creating it, or
#      resetting a branch a failed attempt left behind -- it's bot-owned
#      and has no PR, and a stale base would conflict with later develop
#      changes), then add one commit through the GraphQL
#      createCommitOnBranch API (signed by GitHub, which develop's
#      signed-commit rule requires) and open the PR.
set -euo pipefail

version=${1:?version}
changelog=${2:?changelog path}
run_url=${3:?run url}
repo=${GH_REPO:?GH_REPO (owner/name)}

branch="release/sync-v${version}"
title="chore(release): sync v${version} to develop"
script_dir=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)

# 1. Already done?
existing=$(gh pr list --head "$branch" --base develop --state all --json number,state,url \
  --jq '[.[] | select(.state == "OPEN" or .state == "MERGED")][0] | select(. != null) | "\(.state) \(.url)"')
if [[ -n "$existing" ]]; then
  echo "Sync PR already exists (${existing}); nothing to do."
  exit 0
fi

# 2. Anything to sync?
develop_sha=$(gh api "repos/${repo}/git/ref/heads/develop" --jq .object.sha)
gh api "repos/${repo}/contents/server/pyproject.toml?ref=${develop_sha}" --jq .content |
  base64 -d > "${work}/develop-pyproject.toml"
# develop may not have a CHANGELOG.md yet: a 404 compares as an empty file.
# Any other API failure (auth, rate limit, 5xx) fails the step instead of
# passing for "no changelog". Only gh's stderr, "gh: Not Found (HTTP 404)",
# identifies a missing file: on any failure gh exits 1 and writes the raw
# error JSON to stdout (--jq only applies to a successful response).
if changelog_b64=$(gh api "repos/${repo}/contents/CHANGELOG.md?ref=${develop_sha}" \
  --jq .content 2> "${work}/changelog.err"); then
  printf '%s' "$changelog_b64" | base64 -d > "${work}/develop-changelog.md"
elif grep -q '(HTTP 404)' "${work}/changelog.err"; then
  : > "${work}/develop-changelog.md"
else
  echo "::error::Could not read CHANGELOG.md on develop:" >&2
  cat "${work}/changelog.err" >&2
  exit 1
fi

develop_version=$(python3 -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' \
  "${work}/develop-pyproject.toml")
if [[ "$develop_version" == "$version" ]] && cmp -s "${work}/develop-changelog.md" "$changelog"; then
  echo "develop already has v${version} and this CHANGELOG.md; no sync PR needed."
  exit 0
fi

# 3. Branch at current develop, one signed commit, PR.
if gh api "repos/${repo}/git/ref/heads/${branch}" > /dev/null 2>&1; then
  echo "Resetting ${branch} (left by an earlier attempt, no PR) to develop ${develop_sha}."
  gh api -X PATCH "repos/${repo}/git/refs/heads/${branch}" -f "sha=${develop_sha}" -F force=true > /dev/null
else
  gh api -X POST "repos/${repo}/git/refs" -f "ref=refs/heads/${branch}" -f "sha=${develop_sha}" > /dev/null
fi

python3 "${script_dir}/sync_release_payload.py" \
  --repo "$repo" --branch "$branch" --head "$develop_sha" --version "$version" \
  --pyproject "${work}/develop-pyproject.toml" --changelog "$changelog" > "${work}/payload.json"
gh api graphql --input "${work}/payload.json" --jq .data.createCommitOnBranch.commit.url

gh pr create --base develop --head "$branch" --title "$title" --body-file - << EOF
## Developer:
github-actions (release workflow)

## Summary of Proposed Changes
Syncs release v${version} back to develop: \`server/pyproject.toml\` version and the regenerated \`CHANGELOG.md\`. Release: ${GITHUB_SERVER_URL:-https://github.com}/${repo}/releases/tag/v${version}

## Type of Change
- [x] Release housekeeping (no code changes)

## Testing
No image was built for this release; the develop build was promoted by retag. Workflow run: ${run_url}
EOF
