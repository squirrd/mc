# Release Log

Tracks branches that failed the test suite during release builds.

| Date (UTC) | Version | Branch | Status | Notes |
|------------|---------|--------|--------|-------|
| 2026-03-26 12:48 | 2.0.9 | `fix/stale-integration-test-apis` | ❌ Failed | Merge conflict — manual resolution required |
| 2026-04-01 | 2.0.10 | `fix/stale-integration-test-apis` | ❌ Failed | Merge conflict in tests/integration/test_case_terminal.py and test_window_tracking.py — manual resolution required |
| 2026-04-01 | 2.0.10 | `fix/update-checks-wrong-package` | ❌ Failed | 4 unit test failures: test_uptime_calculation_days, test_run_upgrade_uses_list_form_not_shell, test_get_version_resolves_mc_cli_package_not_mc, test_get_version_falls_back_to_uv_tool_list_when_metadata_absent |
| 2026-04-01 | 2.0.11 | `fix/worktree-venv-isolation` | ⚠️ Included (pre-existing failure) | test_duplicate_terminal_prevention_regression in test_case_terminal.py — unrelated iTerm2 window focus flaky test, not caused by branch changes |
| 2026-04-01 | 2.0.12 | `fix/update-checks-wrong-package` | ✅ Merged | Unit tests aligned to final 'mc' package name direction — 764 passed |
| 2026-04-01 | 2.0.12 | `fix/window-registry-stale-cleanup` | ✅ Merged | Window registry stale cleanup fix — 764 passed |
| 2026-05-11 | 2.0.21 | `fix/agent-base-dir-check` | ❌ Failed | Merge conflict in tests/integration/test_entry_points.py — manual resolution required |
| 2026-05-12 | 2.0.22 | `fix/agent-base-dir-check` | ✅ Merged | Rebased onto main, conflict resolved — 798 passed |
| 2026-05-18 | 2.0.23 | `fix/agent-init-case-path` | ✅ Merged | 812 passed (1 pre-existing: MC-69 proxy detection) |
| 2026-05-18 | 2.0.23 | `fix/agent-auth-mount` | ✅ Merged | 813 passed (2 pre-existing: MC-69 + OCM port 9998) |
| 2026-05-18 | 2.0.23 | `fix/bash-env-host-path` | ✅ Merged | 814 passed (3 pre-existing: MC-69 + OCM port 9998 x2) |
| 2026-05-18 | 2.0.23 | `fix/agent-base-dir-override` | ✅ Merged | 816 passed (4 pre-existing: MC-69 + OCM + iTerm2 websocket x2) |
| 2026-05-19 | 2.0.24 | `fix/ocm-port-guard-tests` | ✅ Merged | 829 passed (3 pre-existing: MC-69 proxy + iTerm2 websocket x2 — fixed by subsequent branches) |
| 2026-05-19 | 2.0.24 | `fix/pac-proxy-detection` | ✅ Merged | 829 passed, 0 failed |
| 2026-05-19 | 2.0.24 | `fix/iterm2-ws-test-guard` | ✅ Merged | 832 passed, 0 failed |
| 2026-05-19 | 2.0.25 | `fix/sfdc-file-save-path` | ✅ Merged | 837 passed, 0 failed |
| 2026-05-19 | 2.0.25 | `fix/claude-container-settings` | ✅ Merged | 840 passed, 0 failed |
