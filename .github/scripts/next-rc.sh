#!/usr/bin/env bash
# Print the release candidate version for the current develop commit, e.g.
# "0.2.0-rc.3", or nothing when no release is pending (only docs/chore/...
# since the last release).
#
# semantic-release (server/pyproject.toml, develop = prerelease branch)
# decides WHETHER a release is pending and its base version X.Y.Z. The rc
# number is always one more than the highest existing vX.Y.Z-rc.* git tag,
# so every develop build of a pending release gets its own rc. (semantic-
# release on its own only moves to a new rc for releasable commits, which
# would leave e.g. a docs-only build without an rc, and the image that gets
# promoted must be one that was published as an rc.)
#
# Must run inside the repo with full history and tags; needs
# python-semantic-release on PATH. Checks out a local `develop` branch at
# HEAD, because semantic-release picks its branch config by branch name.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
git -C "$repo_root" checkout -q -B develop

next=$(cd "$repo_root/server" && semantic-release version --print 2>/dev/null)

if [[ -z "$next" ]]; then
  echo "semantic-release could not compute a version" >&2
  exit 1
fi

# No "-rc." suffix: nothing releasable since the last release.
if [[ "$next" != *-rc.* ]]; then
  exit 0
fi

base=${next%-rc.*}
last_n=$(git -C "$repo_root" tag --list "v${base}-rc.*" | sed -n "s/^v${base//./\\.}-rc\.\([0-9][0-9]*\)$/\1/p" | sort -n | tail -1)

echo "${base}-rc.$((${last_n:-0} + 1))"
