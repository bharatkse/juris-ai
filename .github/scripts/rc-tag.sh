#!/usr/bin/env bash
# Create the annotated release-candidate tag v${RC} on ${GITHUB_SHA},
# recording the exact image digest the rc was published under. Promotion
# reads the digest from this tag and checks the registry still agrees,
# instead of trusting a mutable image tag.
#
# Safe to re-run: if v${RC} already exists on ${GITHUB_SHA} (an earlier
# attempt), it is kept. If it exists on another commit, this fails.
#
# Env: REPO (owner/name), RC (e.g. 0.2.0-rc.1), IMAGE, DIGEST, GITHUB_SHA,
# optional GITHUB_STEP_SUMMARY. Needs an authenticated `gh`.
set -euo pipefail

summary=${GITHUB_STEP_SUMMARY:-/dev/null}

# Print "<object type> <object sha>" for refs/tags/v${RC}, or nothing if the
# tag doesn't exist. Any other API failure (auth, rate limit, 5xx) is an
# error, never "no tag".
#
# The exit status alone can't tell those apart, and stdout can't either:
# when the request fails, gh exits 1 and writes the raw error JSON to
# stdout (--jq only applies to a successful response). Only gh's stderr,
# "gh: Not Found (HTTP 404)", identifies a missing ref.
tag_ref() {
  local ref err
  err=$(mktemp)

  if ref=$(gh api "repos/${REPO}/git/ref/tags/v${RC}" \
    --jq '.object.type + " " + .object.sha' 2> "$err"); then
    rm -f "$err"
    printf '%s\n' "$ref"
    return 0
  fi

  if grep -q '(HTTP 404)' "$err"; then
    rm -f "$err"
    return 0
  fi

  echo "::error::Could not check whether v${RC} exists:" >&2
  cat "$err" >&2
  rm -f "$err"
  return 1
}

ref=$(tag_ref)

if [[ -n "$ref" ]]; then
  read -r ref_type ref_sha <<< "$ref"

  if [[ "$ref_type" == "tag" ]]; then
    # Annotated tag: the ref points at the tag object; peel to its commit.
    tagged=$(gh api "repos/${REPO}/git/tags/${ref_sha}" --jq .object.sha)
  else
    # Lightweight tag: the ref points at the commit itself.
    tagged=$ref_sha
  fi

  if [[ "$tagged" != "$GITHUB_SHA" ]]; then
    echo "::error::v${RC} already exists on ${tagged}, not on ${GITHUB_SHA}."
    exit 1
  fi

  echo "v${RC} already exists on ${GITHUB_SHA} (earlier attempt); keeping it." | tee -a "$summary"
  exit 0
fi

message=$(printf 'Release candidate %s\n\nimage: %s:%s\ndigest: %s\n' "$RC" "$IMAGE" "$RC" "$DIGEST")
tag_object=$(gh api "repos/${REPO}/git/tags" \
  -f "tag=v${RC}" -f "message=${message}" -f "object=${GITHUB_SHA}" -f type=commit --jq .sha)
gh api "repos/${REPO}/git/refs" -f "ref=refs/tags/v${RC}" -f "sha=${tag_object}" > /dev/null
echo "Tagged ${GITHUB_SHA} as v${RC} (${IMAGE}@${DIGEST})" | tee -a "$summary"
