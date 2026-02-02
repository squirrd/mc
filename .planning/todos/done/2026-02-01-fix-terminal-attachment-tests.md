---
created: 2026-02-01T23:44
title: Fix terminal attachment tests
area: testing
files:
  - tests/unit/test_terminal_attach.py
  - src/mc/terminal/attach.py
---

## Problem

17 test failures in terminal attachment functionality (test_terminal_attach.py):

**TestBuildExecCommand:**
- `test_build_exec_command_format`

**TestAttachTerminal (16 failures):**
- `test_attach_terminal_creates_container`
- `test_attach_terminal_starts_stopped_container`
- `test_attach_terminal_launches_terminal`
- `test_attach_terminal_custom_bashrc`
- `test_attach_terminal_window_title`
- `test_attach_terminal_podman_exec_command`
- `test_attach_terminal_not_tty`
- `test_attach_terminal_invalid_case_number`
- `test_attach_terminal_salesforce_failure`
- `test_attach_terminal_container_create_failure`
- `test_attach_terminal_launcher_failure`
- `test_attach_terminal_metadata_fallbacks`
- `test_attach_terminal_workspace_path_fallback`

Significant test coverage failure for terminal attachment - core v2.0 feature. Tests may be outdated after recent fixes to attach.py (Salesforce API method call fix completed 2026-02-01).

## Solution

1. Review test_terminal_attach.py test expectations against current attach.py implementation
2. Update mocks and assertions to match recent fixes (Salesforce method name, container creation)
3. Verify exec command format matches actual Podman API usage
4. Update error handling test cases
