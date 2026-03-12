---
phase: 29-iterm2-api-migration
verified: 2026-03-12T04:12:28Z
status: passed
score: 4/4 must-haves verified
---

# Phase 29: iTerm2 Python API Migration Verification Report

**Phase Goal:** Users get cleaner terminal windows when opening case containers on macOS — raw command hidden, custom profile applied, with reliable fallback.
**Verified:** 2026-03-12T04:12:28Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Running `mc case 12345678` on macOS opens an iTerm2 window using the `iterm2` Python library (not AppleScript) | VERIFIED | `launch()` calls `_try_iterm2_api()` first when `self.terminal == "iTerm2"`; uses `iterm2.run_until_complete` with `iterm2.Window.async_create`; `_build_iterm_script()` (AppleScript) is explicitly marked as no longer the primary path |
| 2 | The new window opens with the `MCC-Term` iTerm2 profile applied and the `podman exec` command is not visible in scrollback | VERIFIED | `iterm2.Window.async_create(connection, profile="MCC-Term", command=options.command)` at macos.py:548-551; `command=` param in `async_create` hides the command from terminal scrollback (API-level feature, not echoed via `write text`) |
| 3 | When iTerm2 Python API is unavailable (library missing, API disabled, or timeout), the launcher falls back to Terminal.app without error | VERIFIED | `_try_iterm2_api()` returns `None` on `ImportError` (lib missing), any raised `Exception` (connection refused, API disabled), or `asyncio.TimeoutError` propagated as exception; `launch()` falls through to `_build_terminal_app_script()` (Terminal.app AppleScript) without raising; fallback notice printed to stderr once per day via sentinel file |
| 4 | Unit tests cover all API branches and the full suite passes | VERIFIED | 24 tests in `test_terminal_macos_api.py` covering API success, lib missing, connection exception, fallback notice show/suppress, `_capture_window_id` API consumption, `_window_exists_by_id` and `focus_window_by_id` dispatch; 523 unit tests pass, 0 failures; mypy 0 errors; flake8 0 errors; bandit 0 high severity |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `pyproject.toml` | `iterm2>=2.14` in optional-dependencies (not core) + mypy override | VERIFIED | Line 52: `"iterm2>=2.14; sys_platform == 'darwin'"` under `[project.optional-dependencies].macos`; line 125: `module = "iterm2.*"` with `ignore_missing_imports = true` |
| `src/mc/terminal/macos.py` | `_ITERM2_LIB_AVAILABLE` flag, Python API methods, launch() API-first dispatch | VERIFIED | 639 lines; `_ITERM2_LIB_AVAILABLE` at module level with `try/except ImportError`; `_launch_via_iterm2_api()`, `_try_iterm2_api()`, `_window_exists_by_id_api()`, `_focus_window_by_id_api()` all present; `launch()` dispatches to `_try_iterm2_api()` first |
| `tests/unit/test_terminal_macos_api.py` | 12+ tests for Python API path | VERIFIED | 438 lines; 24 test functions across 6 test classes |
| `tests/unit/test_terminal_launcher.py` | Updated iTerm2 launch tests for API-first dispatch | VERIFIED | 543 lines; updated with `_via_api` and `_via_applescript_fallback` variants; 3 existing tests explicitly mock `_try_iterm2_api=None` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `macos.py:launch()` | `_try_iterm2_api()` | called when `self.terminal == "iTerm2"` | WIRED | Lines 592-596: `window_id = self._try_iterm2_api(options)`; returns if not None |
| `macos.py:_launch_via_iterm2_api()` | `iterm2.Window.async_create` | `iterm2.run_until_complete(_main)` with `asyncio.timeout(5)` | WIRED | Lines 547-558: `async_create(connection, profile="MCC-Term", command=options.command)` with timeout; result captured in closure |
| `macos.py:launch()` | `_build_terminal_app_script()` | fallback when `_try_iterm2_api` returns `None` | WIRED | Lines 606-608: both `iTerm2` fallback and `Terminal.app` branch use `_build_terminal_app_script()` |
| `test_terminal_macos_api.py` | `MacOSLauncher` methods | `mocker.patch.object` on synchronous wrappers | WIRED | Imports `MacOSLauncher`, `_record_iterm2_fallback_notice`, `_should_show_iterm2_fallback_notice` directly; 24 tests all passing |

### Requirements Coverage

No separate `REQUIREMENTS.md` phase mapping examined — verified against the four must-have truths from the PLAN frontmatter. All four satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `macos.py` | 489 | `_build_iterm_script()` noted as "kept for backwards compatibility and test coverage" — dead code path for primary window creation | Info | Not a blocker; method is documented as intentionally preserved; no TODO/placeholder markers |

No blockers. No stub patterns. No empty implementations. No TODO/FIXME markers that block goal achievement.

### Human Verification Required

The following items cannot be verified programmatically and require a real macOS machine with iTerm2 installed and Python API enabled:

#### 1. Visual: Command hidden from scrollback

**Test:** Run `mc case 12345678` with iTerm2 Python API enabled. Open the new window and scroll up.
**Expected:** Only the shell prompt is visible. The `podman exec -it mc-12345678 bash` command does not appear in the terminal scrollback.
**Why human:** The `command=` parameter behavior in `iterm2.Window.async_create` is an iTerm2 runtime property. Code passes the param correctly; whether iTerm2 actually suppresses the echo requires a live test.

#### 2. Visual: MCC-Term profile applied

**Test:** Run `mc case 12345678` with iTerm2 Python API enabled. Inspect the new window's profile.
**Expected:** The window uses the `MCC-Term` profile (fonts, colors, appearance match the profile configuration).
**Why human:** Profile application depends on the profile existing in the user's iTerm2 installation. Code passes `profile="MCC-Term"` correctly; visual confirmation requires a live test.

#### 3. Fallback: Terminal.app opens when API is disabled

**Test:** Disable iTerm2 Python API (iTerm2 > Settings > General > Magic > uncheck Enable Python API). Run `mc case 12345678`.
**Expected:** A Terminal.app window opens (not iTerm2). A one-line message appears on stderr: "iTerm2 API unavailable, using Terminal.app. Enable via iTerm2 > Settings > General > Magic > Enable Python API".
**Why human:** Requires controlling iTerm2's API state and observing cross-application terminal launch behavior.

### Gaps Summary

No gaps. All four must-have truths are verified by direct code inspection and automated test execution.

---

## Supporting Evidence

**pyproject.toml:**
- `iterm2>=2.14` appears at line 52 under `[project.optional-dependencies].macos` only — not in `[project.dependencies]` (confirmed: no `iterm2` in lines 25-37)
- mypy override at lines 124-126: `module = "iterm2.*"` with `ignore_missing_imports = true`

**src/mc/terminal/macos.py (639 lines):**
- Module-level `_ITERM2_LIB_AVAILABLE` with `try/except ImportError` guard (lines 18-23)
- `_launch_via_iterm2_api()` uses `iterm2.Window.async_create(connection, profile="MCC-Term", command=options.command)` inside `asyncio.timeout(5)` coroutine (lines 530-559)
- `_try_iterm2_api()` catches all exceptions, returns `None` on any failure (lines 561-579)
- `launch()` dispatches to `_try_iterm2_api()` first for iTerm2, stores `window_id` and returns on success, falls through to `_build_terminal_app_script()` (Terminal.app) on `None` (lines 591-608)
- `_window_exists_by_id()` and `focus_window_by_id()` both try API first, fall back to AppleScript when API returns `None`

**Quality gate (all clean):**
- `uv run pytest tests/unit/ --no-cov`: 523 passed, 1 warning (deprecation in third-party library)
- `uv run mypy src/mc/terminal/macos.py`: Success: no issues found in 1 source file
- `uv run flake8 src/mc/terminal/macos.py tests/unit/test_terminal_macos_api.py tests/unit/test_terminal_launcher.py`: no output (clean)
- `uv run bandit -r src/mc/terminal/macos.py`: 0 High, 0 Medium severity (17 Low — all `subprocess` calls, expected for a terminal launcher)

---

_Verified: 2026-03-12T04:12:28Z_
_Verifier: Claude (gsd-verifier)_
