#!/usr/bin/env bash
# Print image tags, one full reference per line.
#
# Usage: image-tags.sh <image> <mode> <sha> [version]
#   mode=develop  (the only build) [:X.Y.Z-rc.N if version given], :develop, :sha-<7>
#   mode=release  (promotion retag) :X.Y.Z, :X.Y, :X (only once X >= 1), :latest, :sha-<7>
#
# Called by publish-image.yaml and promote-image.sh; runnable locally.
set -euo pipefail

image=${1:?image}
mode=${2:?mode (develop|release)}
sha=${3:?commit sha}
version=${4:-}

short_sha=${sha:0:7}

case "$mode" in
  develop)
    if [[ -n "$version" ]]; then
      if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$ ]]; then
        echo "develop mode takes an X.Y.Z-rc.N version (or none), got '${version}'" >&2
        exit 1
      fi
      printf '%s\n' "${image}:${version}"
    fi
    printf '%s\n' "${image}:develop" "${image}:sha-${short_sha}"
    ;;
  release)
    if [[ ! "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
      echo "release mode needs a plain X.Y.Z version, got '${version}'" >&2
      exit 1
    fi
    major=${BASH_REMATCH[1]}
    minor=${BASH_REMATCH[2]}
    printf '%s\n' "${image}:${version}" "${image}:${major}.${minor}"
    # A floating :0 tag would move across breaking 0.x releases.
    if ((major >= 1)); then
      printf '%s\n' "${image}:${major}"
    fi
    printf '%s\n' "${image}:latest" "${image}:sha-${short_sha}"
    ;;
  *)
    echo "unknown mode '${mode}' (expected develop|release)" >&2
    exit 1
    ;;
esac
