#!/usr/bin/env bash
# Scan a locally built image with Trivy and gate on it.
#
# Gate (same as the Phase A baseline): fail on HIGH/CRITICAL findings that
# have a fixed version (--ignore-unfixed). Findings with no upstream fix
# don't block, and start failing automatically once a fix ships.
# .trivyignore.yaml (repo root) is honoured if present; there is none today.
#
# Usage: trivy-gate.sh <image-ref> <out-dir>
# Writes <out-dir>/trivy.sarif (all HIGH/CRITICAL, for the Security tab)
# and <out-dir>/trivy-table.txt (gating findings, for the job summary).
# Exit status: 0 = gate passed, 1 = gating findings, 2 = the scan itself
# failed (Trivy error, DB download, ...), so callers never mistake a broken
# scan for a vulnerability or a pass. Needs Docker; runnable locally.

# Trivy's own errors also exit 1, so findings are signalled with a distinct
# code and mapped back to 1 below.
readonly FINDINGS_EXIT=5
set -euo pipefail

image=${1:?image ref}
out_dir=${2:?output dir}
trivy_version=${TRIVY_VERSION:-0.58.1}
cache_dir=${TRIVY_CACHE_DIR:-${HOME}/.cache/trivy}
repo_root=$(cd "$(dirname "$0")/../.." && pwd)

mkdir -p "$out_dir" "$cache_dir"
out_dir=$(cd "$out_dir" && pwd)

ignore_args=()
if [[ -f "${repo_root}/.trivyignore.yaml" ]]; then
  ignore_args=(--ignorefile /repo/.trivyignore.yaml)
fi

# Run as the calling user (plus the docker socket's group) so the cache and
# results are owned by that user: files Trivy writes as root (e.g. a 0700
# fanal/ dir) can't be read back by actions/cache or cleaned up.
trivy() {
  docker run --rm \
    --user "$(id -u):$(id -g)" \
    --group-add "$(stat -c %g /var/run/docker.sock)" \
    -e HOME=/tmp \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${cache_dir}:/cache" \
    -v "${repo_root}:/repo:ro" \
    -v "${out_dir}:/out" \
    "aquasec/trivy:${trivy_version}" image \
    --cache-dir /cache \
    --quiet --timeout 25m --scanners vuln --severity HIGH,CRITICAL \
    "${ignore_args[@]}" "$@" "$image"
}

# Report everything HIGH/CRITICAL, fixable or not.
if ! trivy --format sarif --output /out/trivy.sarif; then
  echo "Trivy scan of ${image} failed (see above)." >&2
  exit 2
fi

# The gate: only findings with a fix.
set +e
trivy --ignore-unfixed --format table --output /out/trivy-table.txt --exit-code "$FINDINGS_EXIT"
status=$?
set -e

case "$status" in
  0)
    echo "Trivy gate passed: no fixable HIGH/CRITICAL findings in ${image}."
    ;;
  "$FINDINGS_EXIT")
    echo "Trivy gate FAILED: fixable HIGH/CRITICAL findings in ${image}:" >&2
    cat "${out_dir}/trivy-table.txt" >&2
    exit 1
    ;;
  *)
    echo "Trivy scan of ${image} failed (exit ${status}, see above)." >&2
    exit 2
    ;;
esac
