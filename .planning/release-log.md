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
