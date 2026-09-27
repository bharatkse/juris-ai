#!/usr/bin/env bash
# Open the release PR: release/cut-vX.Y.Z (at develop's HEAD) -> main.
# Merging that PR is what releases (promote + release jobs in
# ci-server.yml); this script never merges anything.
#
# Usage: cut-release.sh [expected-version]
# Needs GH_TOKEN and GH_REPO; run from the repo root with full history and
# tags, origin/develop and origin/main fetched, and python-semantic-release
# installed (resolve-release.sh uses it).
#
# Refuses (non-zero exit, clear message) when:
#   - a PR into main is already open (finish or close it first);
#   - develop's HEAD is already released, or already on main;
#   - nothing releasable is pending, or develop's HEAD has no release
#     candidate yet (its develop build hasn't published one);
#   - expected-version is given and isn't what would be released.
set -euo pipefail

expected=${1:-}
repo=${GH_REPO:?GH_REPO (owner/name)}
script_dir=$(cd "$(dirname "$0")" && pwd)

fail() {
  echo "::error::$*"
  exit 1
}

develop_sha=$(git rev-parse origin/develop)

# One release in flight at a time.
open_pr=$(gh pr list --base main --state open --json number,headRefName,url \
  --jq '.[0] | select(. != null) | "#\(.number) from \(.headRefName): \(.url)"')
[[ -z "$open_pr" ]] || fail "A PR into main is already open (${open_pr}). Merge or close it before cutting another release."

# Nothing new to ship?
released_as=$(git tag --points-at "$develop_sha" --list 'v[0-9]*' | grep -Ev -- '-rc\.[0-9]+$' | head -n 1 || true)
[[ -z "$released_as" ]] || fail "develop's HEAD (${develop_sha}) is already released as ${released_as}; nothing new to ship."
if git merge-base --is-ancestor "$develop_sha" origin/main; then
  fail "main already contains develop's HEAD (${develop_sha}); nothing new to ship."
fi

# Exactly what merging would release: the same resolution promotion runs.
resolution=$("${script_dir}/resolve-release.sh" "$develop_sha") ||
  fail "develop's HEAD (${develop_sha}) can't be released yet (see above)."
released=$(sed -n 's/^released=//p' <<< "$resolution")
version=$(sed -n 's/^version=//p' <<< "$resolution")
rc_tag=$(sed -n 's/^rc_tag=//p' <<< "$resolution")
digest=$(sed -n 's/^digest=//p' <<< "$resolution")

[[ "$released" == true ]] || fail "Nothing releasable on develop since the last release (only docs/chore/... commits)."
if [[ -n "$expected" && "${expected#v}" != "$version" ]]; then
  fail "Expected v${expected#v}, but develop's HEAD would release v${version} (${rc_tag}). The version comes from the release candidate being promoted; check the input."
fi

branch="release/cut-v${version}"
owner=${repo%%/*}
image="ghcr.io/${owner,,}/juris-ai"

# No open PR (checked above), so any existing branch is a leftover from a
# closed PR: point it at develop's HEAD again.
if gh api "repos/${repo}/git/ref/heads/${branch}" > /dev/null 2>&1; then
  gh api -X PATCH "repos/${repo}/git/refs/heads/${branch}" -f "sha=${develop_sha}" -F force=true > /dev/null
else
  gh api -X POST "repos/${repo}/git/refs" -f "ref=refs/heads/${branch}" -f "sha=${develop_sha}" > /dev/null
fi

pr_url=$(gh pr create --base main --head "$branch" --title "release: v${version}" --body-file - << EOF
## Developer:
github-actions (cut-release workflow)

## Summary of Proposed Changes
Releases **v${version}** by promoting release candidate \`${rc_tag}\` from develop.

- Source commit (develop HEAD): \`${develop_sha}\`
- Image to promote: \`${image}@${digest}\` (not rebuilt)

Merging this PR (**Create a merge commit**) runs the release: the rc is verified and re-scanned, retagged as \`${version}\`/\`latest\`, tagged \`v${version}\` with a GitHub Release and SBOM, and a sync PR back to develop is opened.

## Type of Change
- [x] Release

## Testing
The source commit passed CI, smoke/e2e and the image scan on develop. Add the \`run-image-scan\` label to run the promotion checks as a dry run on this PR.
EOF
)

echo "Opened ${pr_url} (v${version} = ${rc_tag}, ${develop_sha})."
echo "pr_url=${pr_url}" >> "${GITHUB_OUTPUT:-/dev/null}"
echo "version=${version}" >> "${GITHUB_OUTPUT:-/dev/null}"
