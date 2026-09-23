#!/bin/bash
input=$(cat)
message=$(echo "$input" | jq -r '.message // "Needs your attention"')
seq=$(printf '\033]777;notify;Claude Code;%s\007' "$message")
jq -nc --arg seq "$seq" '{terminalSequence: $seq}'
