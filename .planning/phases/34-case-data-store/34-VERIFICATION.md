---
phase: 34-case-data-store
verified: 2026-03-20T11:39:31Z
status: passed
score: 6/6 must-haves verified
---

# Phase 34: Case Data Store Verification Report

**Phase Goal:** Extract all available case metadata from the Red Hat API and write it to case.json + case.env inside the case workspace before/during terminal attachment.
**Verified:** 2026-03-20T11:39:31Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | sfdc-case.json written by init_case_data() | VERIFIED | `case_data.py:70` — `json.dump(case_details, f, indent=2)` writes full raw API response to `sfdc-case.json` on every call |
| 2 | case.env written by init_case_data() | VERIFIED | `case_data.py:88-99` — builds and writes 8-line env file with all required fields |
| 3 | Both files contain required fields | VERIFIED | All 7 required fields present: `MC_CASE_NUMBER`, `MC_CLUSTER_EXTERNAL_ID`, `MC_CUSTOMER_NAME`, `MC_SUMMARY`, `MC_SEVERITY`, `MC_STATUS`, `MC_PRODUCT` |
| 4 | Files refreshed on every mc case N invocation | VERIFIED | `attach.py:82` — `build_exec_command()` returns command ending in `/bin/bash -c 'mc agent init-case \|\| true; exec bash'`; `|| true` ensures shell always opens |
| 5 | cluster_id present even when API returns none | VERIFIED | `case_data.py:79` — `cluster_external_id = str(case_details.get("openshiftClusterID") or "")` — defaults to `""`, written as `MC_CLUSTER_EXTERNAL_ID=""` |
| 6 | Unit tests cover file writing and field extraction | VERIFIED | `test_agent_case_data.py` — 22 tests across 5 classes covering file writing, env format, OCM behavior, and all failure paths; 3 new init-case tests in `test_terminal_attach.py` |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mc/agent/case_data.py` | Core file-writing logic | VERIFIED | 121 lines, substantive, exports `init_case_data()`, no stubs |
| `src/mc/cli/commands/agent.py` | CLI entry point for `mc agent init-case` | VERIFIED | 25 lines, reads `CASE_NUMBER` env var, calls `init_case_data()` |
| `src/mc/cli/main.py` | CLI routing for `agent init-case` subcommand | VERIFIED | `agent_subparsers.add_parser('init-case', ...)` at line 117; dispatches to `init_case()` at lines 200-202 |
| `src/mc/terminal/attach.py` | `build_exec_command()` prepends init-case | VERIFIED | 373 lines; line 82 contains `/bin/bash -c 'mc agent init-case \|\| true; exec bash'` |
| `tests/unit/test_agent_case_data.py` | Tests for case_data module | VERIFIED | 301 lines, 22 tests across 5 classes, all substantive assertions |
| `tests/unit/test_terminal_attach.py` | Tests for attach with init-case | VERIFIED | 619 lines, includes 3 new init-case-specific tests at lines 104-123 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/mc/terminal/attach.py` | `mc agent init-case` (in container) | `podman exec ... /bin/bash -c 'mc agent init-case \|\| true; exec bash'` | WIRED | Line 82 of attach.py contains exact string |
| `src/mc/cli/commands/agent.py` | `src/mc/agent/case_data.py` | `from mc.agent.case_data import init_case_data` + `init_case_data(case_number)` | WIRED | Lines 18 and 25 of agent.py |
| `src/mc/cli/main.py` | `src/mc/cli/commands/agent.py` | `agent_subparsers.add_parser('init-case', ...)` + dispatch | WIRED | Lines 117, 200-202 of main.py |
| `case_data.py` | `/case/sfdc-case.json` | `json.dump(case_details, f, indent=2)` | WIRED | Line 70-71; full API response serialized |
| `case_data.py` | `/case/case.env` | `f.write("\n".join(lines) + "\n")` | WIRED | Lines 88-99; all 7 fields written |

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| CDS-01: sfdc-case.json written to /case/ at terminal attach time | SATISFIED | `case_data.py:70`; triggered via `mc agent init-case` in `build_exec_command()` |
| CDS-02: case.env written to /case/ in KEY=VALUE bash-source format | SATISFIED | `case_data.py:88-99`; `KEY="value"` format, double-quoted; verified by `test_case_env_all_values_double_quoted` |
| CDS-03: case.env includes all required fields | SATISFIED | All 7 fields present: case_number, cluster_external_id, customer_name, summary, severity, status, product |
| CDS-04: Files overwritten on every mc case N | SATISFIED | `build_exec_command()` runs `mc agent init-case` every invocation (no skip-if-exists logic in `case_data.py`); `test_files_overwritten_on_each_call` verifies this |
| CDS-05: MC_CLUSTER_EXTERNAL_ID always present, even when empty | SATISFIED | `case_data.py:79`; `or ""` fallback; `test_case_env_mc_cluster_external_id_present_when_empty` verifies `MC_CLUSTER_EXTERNAL_ID=""` is written |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No stubs, TODOs, or empty implementations found in phase files |

### Human Verification Required

None — all success criteria are verifiable programmatically. The one behavioral item that requires a real container (that `mc agent init-case` actually runs at attach time) is structurally verified: `build_exec_command()` returns the exact command string and the test at line 55 in `test_terminal_attach.py` asserts the exact suffix `"mc-12345678 /bin/bash -c 'mc agent init-case || true; exec bash'; exit"`.

### Test Run Result

46 tests run across `test_agent_case_data.py` and `test_terminal_attach.py` — all pass.

### Summary

Phase 34 goal is fully achieved. The implementation is complete and connected end-to-end:

1. `build_exec_command()` in `attach.py` prepends `mc agent init-case || true` before the interactive shell on every `mc case N` invocation.
2. The CLI routes `mc agent init-case` to `init_case()` in `cli/commands/agent.py`, which reads `CASE_NUMBER` from the environment and calls `init_case_data()`.
3. `init_case_data()` in `agent/case_data.py` fetches case details from the Red Hat API, writes `sfdc-case.json` (full raw JSON), and writes `case.env` with all 7 required MC-prefixed variables including `MC_CLUSTER_EXTERNAL_ID` (always present, defaulting to `""` when the API returns no cluster ID).
4. All failure paths are non-fatal — the interactive shell always opens even if `mc agent init-case` fails.
5. 22 unit tests in `test_agent_case_data.py` cover file writing, env format, OCM conditional behavior, and failure handling. 3 new tests in `test_terminal_attach.py` assert the init-case integration in `build_exec_command()`.

---
*Verified: 2026-03-20T11:39:31Z*
*Verifier: Claude (gsd-verifier)*
