#!/usr/bin/env bash
# Promote an already-built, already-scanned, already-signed release
# candidate to its release tags. Never rebuilds or re-signs.
#
# Usage: promote-image.sh <image> <rc> <digest> <source-sha> <version> <push> <sbom-out>
#   image       ghcr.io/owner/juris-ai
#   rc          X.Y.Z-rc.N (image tag of the candidate)
#   digest      sha256:... recorded by the develop build
#   source-sha  develop commit the candidate was built from
#   version     X.Y.Z to release
#   push        true = add the release tags; false = verify only (dry run)
#   sbom-out    where to write the signed SBOM (SPDX JSON)
#
# Checks, in order (any failure exits non-zero, nothing is tagged):
#   1. :<rc> still resolves to <digest> (registry agrees with the git tag)
#   2. the image's revision label is <source-sha>
#   3. the signature and SPDX SBOM attestation verify, and were made by the
#      develop build of <source-sha>
#   4. re-scan: the image, pulled by digest (no rebuild, nothing pushed),
#      still passes the same Trivy gate as the build (trivy-gate.sh), so a
#      CVE disclosed since the rc was built blocks the release
# Then (push=true) `crane tag` adds each release tag to <digest>. crane
# re-uses the exact manifest bytes, so the digest (and every signature and
# attestation stored against it) is unchanged; this is re-checked after.
#
# Keyless verification by default. COSIGN_VERIFY_ARGS / CRANE_ARGS replace
# the defaults (local testing with a key and an http registry). Re-scan
# results go to PROMOTE_SCAN_DIR (default: trivy-promotion).
set -euo pipefail

image=${1:?image}
rc=${2:?rc}
digest=${3:?digest}
source_sha=${4:?source sha}
version=${5:?version}
push=${6:?push true|false}
sbom_out=${7:?sbom output path}

script_dir=$(cd "$(dirname "$0")" && pwd)
read -r -a crane_args <<< "${CRANE_ARGS:-}"

if [[ -n "${COSIGN_VERIFY_ARGS:-}" ]]; then
  read -r -a verify_args <<< "$COSIGN_VERIFY_ARGS"
else
  repo=${GITHUB_REPOSITORY:?GITHUB_REPOSITORY (or COSIGN_VERIFY_ARGS)}
  verify_args=(
    --certificate-identity "https://github.com/${repo}/.github/workflows/publish-image.yaml@refs/heads/develop"
    --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
    --certificate-github-workflow-sha "$source_sha"
  )
fi

ref="${image}@${digest}"

echo "1. :${rc} -> ${digest}?"
actual=$(crane digest "${image}:${rc}" "${crane_args[@]}")
if [[ "$actual" != "$digest" ]]; then
  echo "   ${image}:${rc} is ${actual}, but the rc tag recorded ${digest}." >&2
  exit 1
fi

echo "2. built from ${source_sha}?"
revision=$(crane config --platform linux/amd64 "$ref" "${crane_args[@]}" |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["config"]["Labels"].get("org.opencontainers.image.revision", ""))')
if [[ "$revision" != "$source_sha" ]]; then
  echo "   image revision label is '${revision}', expected ${source_sha}." >&2
  exit 1
fi

echo "3. signature and SBOM attestation"
cosign verify "${verify_args[@]}" "$ref" > /dev/null
cosign verify-attestation --type spdxjson "${verify_args[@]}" "$ref" |
  head -n 1 |
  python3 -c 'import base64, json, sys; print(json.dumps(json.loads(base64.b64decode(json.load(sys.stdin)["payload"]))["predicate"], indent=2))' \
    > "$sbom_out"

echo "4. re-scan (same gate as the build, no rebuild)"
# Pull by digest into the local daemon only, so Trivy scans exactly the
# image being promoted. Nothing is pushed.
docker pull -q "$ref" > /dev/null
scan_status=0
"${script_dir}/trivy-gate.sh" "$ref" "${PROMOTE_SCAN_DIR:-trivy-promotion}" || scan_status=$?
case "$scan_status" in
  0) ;;
  1)
    echo "   ${ref} passed the gate when it was built but fails it now: a fixable HIGH/CRITICAL vulnerability has been disclosed since. Not promoting. Merge the fix to develop to build a new rc." >&2
    exit 1
    ;;
  *)
    echo "   The re-scan of ${ref} couldn't complete, so it's unverified. Not promoting; re-run once the scan works." >&2
    exit 1
    ;;
esac

mapfile -t tags < <("${script_dir}/image-tags.sh" "$image" release "$source_sha" "$version")

if [[ "$push" != true ]]; then
  echo "Dry run: would tag ${ref} as:"
  printf '   %s\n' "${tags[@]}"
  exit 0
fi

for full in "${tags[@]}"; do
  crane tag "$ref" "${full##*:}" "${crane_args[@]}"
done

echo "5. release tags -> ${digest}?"
for full in "${tags[@]}"; do
  got=$(crane digest "$full" "${crane_args[@]}")
  if [[ "$got" != "$digest" ]]; then
    echo "   ${full} is ${got}, expected ${digest}." >&2
    exit 1
  fi
done
cosign verify "${verify_args[@]}" "${image}:${version}" > /dev/null

echo "Promoted ${ref} as:"
printf '   %s\n' "${tags[@]}"
