#!/bin/bash
# Runs unit tests when Claude finishes a turn. On failure, blocks the stop once
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

output=$(make test-unit 2>&1)
if [[ $? -eq 0 ]]; then
  # Fingerprint after the run so files the test run itself creates don't count
  [[ -n "$state_file" ]] && fingerprint > "$state_file"
  log "ran: passed"
  exit 0
fi

log "ran: failed (stop_hook_active=$stop_hook_active)"
summary=$(echo "$output" | grep -E '^(FAILED|ERROR) |[0-9]+ (failed|passed|errors?)' | tail -20)
summary=${summary:-$(echo "$output" | tail -20)}
if [[ "$stop_hook_active" == "true" ]]; then
  jq -n --arg msg "Unit tests still failing after retry:
$summary" '{systemMessage: $msg}'
else
  jq -n --arg reason "Unit tests failed (make test-unit). Fix them if you can; you get one retry before stopping is allowed:
$summary" '{decision: "block", reason: $reason}'
fi

exit 0
