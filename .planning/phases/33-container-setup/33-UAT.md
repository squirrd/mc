---
status: testing
phase: 33-container-setup
source: [33-01-SUMMARY.md, 33-02-SUMMARY.md]
started: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
---

## Current Test

number: 1
name: Claude Code in Container Image
expected: |
  Build the container image and exec into it. Run `claude --version`.
  The command should return a version string (e.g., "2.1.80" or similar).
  Claude Code CLI is installed and callable inside the container.
awaiting: user response

## Tests

### 1. Claude Code in Container Image
expected: Build container and run `claude --version` inside — version string printed, no error
result: [pending]

### 2. nodejs Runtime in Container
expected: Inside the container, `node --version` returns a version string. nodejs is present because the claude wrapper script requires it.
result: [pending]

### 3. mc/config Mount — Read-Only Access
expected: After starting a case container, exec in and verify `/home/mcuser/mc/config` exists and contains the same files as `~/mc/config` on the host (e.g., config.toml). The mount should be read-only (writing should fail or be denied).
result: [pending]

### 4. ~/.claude Mount — Read-Write When Present
expected: If `~/.claude` exists on the host, exec into the container and verify `/home/mcuser/.claude` exists with the same contents. Writing a file there should succeed (read-write mount).
result: [pending]

### 5. mc/config Pre-flight: Hard Fail
expected: If `~/mc/config` does not exist on the host, running `mc case <number>` (or `mc <number>`) should immediately fail with a clear error message before creating any workspace directories. No container is started.
result: [pending]

### 6. ~/.claude Optional: Warn and Continue
expected: If `~/.claude` does not exist on the host, creating a container should still succeed — it starts normally. A warning is logged (visible with `mc --debug`) but the container is not blocked.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0

## Gaps

[none yet]
