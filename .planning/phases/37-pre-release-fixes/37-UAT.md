---
status: testing
phase: 37-pre-release-fixes
source: 37-01-SUMMARY.md, 37-02-SUMMARY.md, 37-03-SUMMARY.md
started: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
---

## Current Test

number: 1
name: Cluster ID persists across sessions (BPL-04)
expected: |
  Enter a cluster ID at the prompt during one mc case N session.
  Close that terminal. Run mc case N again.
  The prompt should NOT appear — backplane login should run automatically
  using the saved cluster ID from the previous session.
awaiting: user response

## Tests

### 1. Cluster ID persists across sessions (BPL-04)
expected: Enter cluster ID at prompt in one session; on next mc case N invocation the prompt is skipped and ocm backplane login runs automatically with the stored ID
result: [pending]

### 2. No update banner in agent mode
expected: Run any mc command (e.g. mc --help) from inside a running container; no Rich Panel update notification banner appears on stderr
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0

## Gaps

[none yet]
