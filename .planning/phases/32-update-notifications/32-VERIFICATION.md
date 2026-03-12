---
phase: 32-update-notifications
verified: 2026-03-12T11:13:39Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 32: Update Notifications Verification Report

**Phase Goal:** Users are informed of available updates at CLI startup without being spammed — banner appears at most once per calendar day, shows modified message when pinned, and never delays CLI beyond 1-2s.
**Verified:** 2026-03-12T11:13:39Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                      | Status     | Evidence                                                                                   |
|----|--------------------------------------------------------------------------------------------|------------|--------------------------------------------------------------------------------------------|
| 1  | When newer MC version is available, Rich Panel banner appears on stderr at CLI startup      | VERIFIED  | `_render_banner()` uses `Console(stderr=True)` + `Panel`; wired into `main()` at line 151 |
| 2  | Banner does not appear more than once per calendar day                                      | VERIFIED  | `_already_shown_today()` compares `.date()` portion of stored ISO timestamp to `date.today()` |
| 3  | When version pin active and newer version exists, banner shows modified message + unpin instruction | VERIFIED  | `_render_banner()` branches on `pinned` arg; "pinned at v{current}" + "mc-update unpin" text |
| 4  | Banner check completes within 1-2s; on timeout a brief note is printed and command runs     | VERIFIED  | Daemon thread with `done.wait(timeout=1.5)`; timeout path prints "Update check timed out." to stderr |
| 5  | `mc --version` suppresses the banner entirely                                              | VERIFIED  | Argparse `action='version'` calls `sys.exit(0)` at `parse_args()` (line 115) before banner call (line 151); `_is_version_invocation()` guard in `banner.py` is belt-and-suspenders |
| 6  | Non-interactive (piped) runs do not trigger suppression timestamp                          | VERIFIED  | `_write_suppression_timestamp()` guards with `sys.stdout.isatty()` check; `show_update_banner()` also guards with `sys.stdout.isatty()` and returns early before any network call |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact                              | Expected                                          | Status    | Details                                                  |
|---------------------------------------|---------------------------------------------------|-----------|----------------------------------------------------------|
| `src/mc/banner.py`                    | Update banner module with `show_update_banner()`  | VERIFIED  | 149 lines, 6 functions, zero stubs, exported             |
| `src/mc/config/manager.py`            | `get_version_config()` returns `last_banner_shown` | VERIFIED  | Lines 172-187 return dict with `last_banner_shown` key; `update_version_config()` accepts and persists it |
| `src/mc/cli/main.py`                  | `show_update_banner()` wired at startup            | VERIFIED  | Imported at line 17; called at line 153 under `get_runtime_mode() != 'agent'` guard |
| `tests/unit/test_banner.py`           | 21-test suite covering all banner functions        | VERIFIED  | 21 tests across 6 classes; all pass (confirmed by run)   |

### Key Link Verification

| From                     | To                              | Via                                     | Status   | Details                                                                 |
|--------------------------|---------------------------------|-----------------------------------------|----------|-------------------------------------------------------------------------|
| `main.py`                | `banner.show_update_banner()`   | Direct import + call at line 151-153    | WIRED    | Under `get_runtime_mode() != 'agent'` guard; exception-safe             |
| `banner._fetch_with_timeout` | `mc.update._fetch_latest_version` | Lazy import inside function; daemon thread | WIRED | Result captured in `result[0]` mutable list; 1.5s `threading.Event` timeout |
| `banner._already_shown_today` | `ConfigManager.get_version_config()` | Lazy import inside function        | WIRED    | Reads `version.last_banner_shown` from TOML config                     |
| `banner._write_suppression_timestamp` | `ConfigManager.update_version_config()` | Lazy import; atomic write   | WIRED    | Writes ISO datetime; gated on `sys.stdout.isatty()`                    |
| `banner._render_banner`  | Rich `Console(stderr=True)` + `Panel` | Lazy import inside function          | WIRED    | Console prints 3 times: blank, panel, blank                             |

### Requirements Coverage

All 6 success criteria map directly to verified truths above. No requirement is blocked.

### Anti-Patterns Found

| File                | Line | Pattern                    | Severity | Impact |
|---------------------|------|----------------------------|----------|--------|
| None found          | -    | -                          | -        | -      |

Stub scan across `src/mc/banner.py`, `src/mc/cli/main.py`, `src/mc/config/manager.py`: no TODO/FIXME, no placeholder content, no empty returns, no console.log-only handlers.

### Human Verification Required

The following items cannot be verified purely from code structure and require a manual run in a real terminal session:

#### 1. Visual appearance of the Rich Panel banner

**Test:** In an interactive TTY, ensure a newer version is available (or mock the version), run `mc ls <any_uid>`, observe stderr output.
**Expected:** A yellow-bordered Rich Panel appears on stderr with title "MC Update Available", blank lines above and below, and either "v{current} → v{latest} / Run: mc-update upgrade" or the pinned variant.
**Why human:** Rich terminal rendering depends on terminal capabilities and cannot be asserted from static analysis.

#### 2. Piped-run suppression timestamp behavior

**Test:** Run `mc ls <any_uid> | cat` (pipes stdout), verify no suppression timestamp is written to config afterwards.
**Expected:** `~/mc/config/config.toml` `[version]` section does not gain or update `last_banner_shown` after the piped run.
**Why human:** The isatty() guard is structurally correct, but end-to-end behavior through real piping needs confirmation.

#### 3. Per-day deduplication across two actual CLI invocations

**Test:** Run any `mc` command twice in the same calendar day (after deleting or backdating `last_banner_shown`). Confirm the banner appears on the first run and not the second.
**Expected:** Second invocation produces no banner; config `last_banner_shown` is set after the first.
**Why human:** Requires real config state transitions across two process invocations.

---

## Verification Notes

### `--version` Suppression — Dual Mechanism

The success criterion says `mc --version` must suppress the banner. This is achieved through two layers:

1. **Primary:** Argparse `action='version'` at line 35 of `main.py` calls `sys.exit(0)` during `parse_args()` at line 115 — before `show_update_banner()` is ever reached at line 151. This is the actual suppression mechanism.

2. **Secondary:** `_is_version_invocation()` in `banner.py` checks `sys.argv[1] == "--version"` and returns early. This is a belt-and-suspenders guard that would matter only if `show_update_banner()` were called before argument parsing (it is not currently, but protects against future refactors).

Both layers are structurally correct. The criterion is met.

### Timeout Boundary

The success criterion states "1-2s". The implementation uses `_TIMEOUT_SECONDS = 1.5`, which is within that range. The daemon thread continues running (detached) after the timeout; only the CLI's wait is bounded to 1.5s.

### `VersionChecker` Still Present

`src/mc/version_check.py` and `src/mc/cli/commands/other.py` still reference `VersionChecker`. This is intentional: `VersionChecker` serves the `mc version --update` manual force-check command, not the startup banner. The startup banner path no longer uses `VersionChecker`.

### Agent Mode Guard

`show_update_banner()` is skipped when `get_runtime_mode() == 'agent'` (i.e., inside a container). This is correct — containers should not attempt outbound version checks on behalf of the host.

---

_Verified: 2026-03-12T11:13:39Z_
_Verifier: Claude (gsd-verifier)_
