#!/bin/bash
# Runs mypy (make type-check) and unit tests when Claude finishes a turn --
# mypy here rather than on each edit, so half-finished multi-file changes
# don't trip it mid-turn. On failure, blocks the stop once
# so Claude can fix it; on the retry (stop_hook_active=true) the stop is always
# allowed and the failure is only reported to the user, so this can't loop.
# Skips the run when the working tree is unchanged since the last green run.
input=$(cat)
stop_hook_active=$(echo "$input" | jq -r '.stop_hook_active // false')
cd "${CLAUDE_PROJECT_DIR}" || exit 0   # Makefile lives at repo root

# Fingerprint = HEAD + tracked changes + untracked (non-ignored) file contents.
# State lives under .git/ so it never shows up in git status.
state_file=$(git rev-parse --git-path claude-last-green 2>/dev/null)
log_file=$(git rev-parse --git-path claude-stop-hook.log 2>/dev/null)
fingerprint() {
  { git rev-parse HEAD; git diff HEAD --binary
    git ls-files -z --others --exclude-standard | xargs -0 -r sha256sum
  } 2>/dev/null | sha256sum | cut -d' ' -f1
}
log() { [[ -n "$log_file" ]] && echo "$(date '+%F %T') $*" >> "$log_file"; }

if [[ -n "$state_file" && -f "$state_file" && "$(cat "$state_file")" == "$(fingerprint)" ]]; then
  log "skipped: no changes since last green run"
  exit 0
fi

# Both always run, so one retry can fix type errors and test failures together
mypy_output=$(make type-check 2>&1); mypy_rc=$?
test_output=$(make test-unit 2>&1); test_rc=$?
if [[ $mypy_rc -eq 0 && $test_rc -eq 0 ]]; then
  # Fingerprint after the run so files the test run itself creates don't count
  [[ -n "$state_file" ]] && fingerprint > "$state_file"
  log "ran: passed"
  exit 0
fi

log "ran: failed (mypy_rc=$mypy_rc test_rc=$test_rc stop_hook_active=$stop_hook_active)"
summary=""
failed=()
if [[ $mypy_rc -ne 0 ]]; then
  failed+=("mypy (make type-check)")
  # Keep only mypy's own lines, not make's banner
  mypy_summary=$(echo "$mypy_output" | grep -E '^src/.*: error:|^Found [0-9]+ errors?' | tail -20)
  summary+="mypy:
${mypy_summary:-$(echo "$mypy_output" | tail -20)}
"
fi
if [[ $test_rc -ne 0 ]]; then
  failed+=("unit tests (make test-unit)")
  test_summary=$(echo "$test_output" | grep -E '^(FAILED|ERROR) |[0-9]+ (failed|passed|errors?)' | tail -20)
  summary+="unit tests:
${test_summary:-$(echo "$test_output" | tail -20)}"
fi
what=$(IFS=,; echo "${failed[*]}" | sed 's/,/ and /')
if [[ "$stop_hook_active" == "true" ]]; then
  jq -n --arg msg "Still failing after retry: $what
$summary" '{systemMessage: $msg}'
else
  jq -n --arg reason "Failed: $what. Fix them if you can; you get one retry before stopping is allowed:
$summary" '{decision: "block", reason: $reason}'
fi

exit 0
