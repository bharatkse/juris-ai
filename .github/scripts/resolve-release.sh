#!/usr/bin/env bash
# Work out what merging develop into main releases: the release candidate
# built for the develop commit being promoted, and the digest it was
# published under.
#
# Usage: resolve-release.sh <source-sha>
#   source-sha = the develop commit being promoted (the release PR's head).
#
# Prints KEY=VALUE lines (for $GITHUB_OUTPUT):
#   released=true|false
#   version=X.Y.Z          rc_tag=vX.Y.Z-rc.N          digest=sha256:...
# released=false (and nothing else) when there is nothing to release.
# Exits non-zero when a release IS pending but can't be promoted safely
# (no rc built for this commit, version mismatch, tag already exists).
#
# Must run inside the repo with full history and tags; needs
# python-semantic-release on PATH.
set -euo pipefail

source_sha=${1:?source sha}
repo_root=$(git rev-parse --show-toplevel)

# Highest rc tag on exactly this commit (a re-run build can add a second).
rc_tag=$(git -C "$repo_root" tag --points-at "$source_sha" --list 'v*-rc.*' | sort -V | tail -1)

# What semantic-release would release from this commit on main.
git -C "$repo_root" checkout -q -B main "$source_sha"
next=$(cd "$repo_root/server" && semantic-release version --print 2>/dev/null)
# The last full release REACHABLE from this commit. Not semantic-release's
# --print-last-released: that reports the newest version tag anywhere in
# the repo, rc tags on later commits included, which made "nothing new
# since the last release" look like "a release is pending but has no rc".
last_tag=$(git -C "$repo_root" describe --tags --abbrev=0 --match 'v[0-9]*' --exclude '*-rc.*' "$source_sha" 2> /dev/null || true)
last=${last_tag#v}

if [[ -z "$rc_tag" ]]; then
  if [[ "$next" == "$last" ]]; then
    echo "released=false"
    exit 0
  fi
  echo "A release (${next}) is pending, but ${source_sha} has no rc tag: its develop build hasn't published an image (still running, or failed). Wait for it, then re-run." >&2
  exit 1
fi

rc=${rc_tag#v}
version=${rc%-rc.*}

if [[ "$next" != "$version" ]]; then
  echo "rc ${rc_tag} implies ${version}, but semantic-release computes ${next} for ${source_sha}." >&2
  exit 1
fi

if git -C "$repo_root" rev-parse -q --verify "refs/tags/v${version}" >/dev/null; then
  echo "v${version} already exists." >&2
  exit 1
fi

# The develop build records the digest it pushed in the annotated rc tag.
digest=$(git -C "$repo_root" tag --list --format='%(contents)' "$rc_tag" | sed -n 's/^digest: \(sha256:[0-9a-f]\{64\}\)$/\1/p')

if [[ -z "$digest" ]]; then
  echo "${rc_tag} doesn't record an image digest (expected a 'digest: sha256:...' line)." >&2
  exit 1
fi

echo "released=true"
echo "version=${version}"
echo "rc_tag=${rc_tag}"
echo "digest=${digest}"
