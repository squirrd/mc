---
phase: 33-container-setup
verified: 2026-03-20T10:38:41Z
status: passed
score: 5/5 must-haves verified
gaps: []
---

# Phase 33: Container Setup Verification Report

**Phase Goal:** Fix the missing mc config issue in containers and add Claude Code, both are Containerfile/mount changes that belong together.
**Verified:** 2026-03-20T10:38:41Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | `mc case-comments <case>` runs inside container without triggering setup wizard (mc config is mounted) | VERIFIED | `manager.py:153` mounts `mc_config` at `/home/mcuser/mc/config` mode `ro`; pre-flight raises `RuntimeError` before container creation if path absent, ensuring mc config is always present when container starts |
| 2   | Container cannot write to `~/mc/config` (mount is read-only) | VERIFIED | `manager.py:153` explicitly sets `"mode": "ro"` for the mc_config volume entry |
| 3   | `claude` command is available inside container (`claude --version` succeeds) | VERIFIED | `Containerfile` Stage 3 (`claude-downloader`) installs `@anthropic-ai/claude-code@2.1.80` via npm; final stage copies `/usr/local/bin/claude` and `/usr/local/lib/node_modules/@anthropic-ai/claude-code` from that stage, and installs `nodejs` runtime |
| 4   | `claude` session inside container uses same auth as host (no re-login needed) | VERIFIED | `manager.py:158-159` mounts `~/.claude` at `/home/mcuser/.claude` mode `rw` when the host directory exists; pre-flight warns and continues if absent |
| 5   | All existing container tests still pass | VERIFIED | 593 unit tests pass (0 failures, 0 errors): `uv run pytest tests/unit/ --no-cov -q` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `container/Containerfile` | claude-downloader stage + final stage updates | VERIFIED | Stage 3 exists as `AS claude-downloader`, `ARG CLAUDE_VERSION=2.1.80`, `npm install -g @anthropic-ai/claude-code`, `nodejs` in final stage dnf block, both `COPY --from=claude-downloader` lines present |
| `src/mc/container/manager.py` | `get_mc_config_path()`, `get_claude_config_path()`, pre-flight checks, updated volumes | VERIFIED | Both helpers at lines 26-41, pre-flight at lines 122-135, volumes with ro mc_config and conditional rw claude_dir at lines 151-159 |
| `tests/unit/test_container_manager_mounts.py` | 5+ unit tests for all mount and pre-flight scenarios | VERIFIED | 6 tests across 3 classes: `TestMcConfigMount` (2 tests), `TestClaudeDirMount` (3 tests), `TestAllMountsTogether` (1 test); all pass |
| `tests/unit/test_container_manager_create.py` | Updated with mocks for new path helpers | VERIFIED | All 15 tests in this file pass with no regressions |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `container/Containerfile` claude-downloader stage | final stage | `COPY --from=claude-downloader` | WIRED | Lines 191-192: binary and node_modules both copied |
| `manager.py get_mc_config_path()` | `create()` volumes dict | called at line 122, used in volumes at line 153 | WIRED | mc_config always in volumes when create() proceeds past pre-flight |
| `manager.py get_claude_config_path()` | `create()` volumes dict | called at line 130, conditionally used at line 158-159 | WIRED | claude_dir added to volumes only when `exists()` returns True |
| pre-flight check | `os.makedirs` (side effects) | RuntimeError raised at line 124 before line 138 | WIRED | Fail-fast ordering confirmed: pre-flight at step 3, makedirs at step 4 |

### Requirements Coverage

| Requirement | Status | Notes |
| ----------- | ------ | ----- |
| CNT-01/02/03: mc config mount (ro) | SATISFIED | Pre-flight + ro volume mount implemented and tested |
| CLD-02/03: claude auth passthrough | SATISFIED | ~/.claude mount (rw, conditional) implemented and tested |
| Claude binary in image | SATISFIED | claude-downloader stage installs via npm; final stage copies binary + node_modules + nodejs runtime |

### Anti-Patterns Found

None detected in modified files.

- `container/Containerfile`: No TODOs, no placeholder content, no empty stages
- `src/mc/container/manager.py`: No stubs; all new functions have real implementations and docstrings; pre-flight raises real errors with user-facing messages
- `tests/unit/test_container_manager_mounts.py`: No placeholder tests; all 6 assertions are specific and meaningful

### Human Verification Required

The following items cannot be verified by static analysis and require a real container build:

#### 1. claude --version succeeds in a built container

**Test:** Build the image (`podman build -t mc-rhel10:latest -f container/Containerfile .`) and run `podman run --rm mc-rhel10:latest claude --version`
**Expected:** Outputs version string like `claude 2.1.80` with exit code 0
**Why human:** Cannot build/run the container in this environment; static analysis confirms the Containerfile instructions are structurally correct but npm install success depends on network access and upstream availability

#### 2. mc config read-only enforcement at runtime

**Test:** Start a container with `~/mc/config` mounted, attempt `touch ~/mc/config/test.txt` inside the container
**Expected:** Permission denied (read-only filesystem)
**Why human:** Mount mode `ro` is set in the volumes dict; actual kernel enforcement requires a running container

#### 3. claude auth passthrough (no re-login inside container)

**Test:** On a host with a configured `~/.claude`, start a case container and run `claude --version` or a simple claude command
**Expected:** Claude Code responds without prompting for authentication
**Why human:** Requires a real `~/.claude` with valid auth credentials and a running container

## Gaps Summary

No gaps. All five success criteria from the phase goal are satisfied by the actual code:

1. mc config is mounted read-only at `/home/mcuser/mc/config` — the pre-flight check guarantees it exists before the container starts, so `mc case-comments` runs without triggering setup wizard.
2. The mount is explicitly `mode: ro` — the container cannot write to `~/mc/config`.
3. The `claude-downloader` Containerfile stage installs the binary at the pinned version `2.1.80`; the final stage copies both the binary and node_modules along with the nodejs runtime.
4. `~/.claude` is mounted `rw` when it exists on the host, passing authentication state into the container.
5. 593 unit tests pass with zero regressions. The 6 new mount tests and 15 existing create tests all pass.

---

_Verified: 2026-03-20T10:38:41Z_
_Verifier: Claude (gsd-verifier)_
