# Phase 30: mc-update Core - Research

**Researched:** 2026-03-12
**Domain:** Python console_scripts entry points, subprocess patterns, CLI error handling
**Confidence:** HIGH

## Summary

Phase 30 adds an `mc-update` command as a separate `console_scripts` entry point in `pyproject.toml`.
The codebase uses `argparse` (not Click or Typer), `subprocess.run()` with `capture_output=True`, and
`print()` / `sys.stderr.write()` for output (no Rich in the new entry point is appropriate). The
version-check infrastructure from Phase 28 (`version_check.py`, `runtime.py`) provides reusable
patterns for guarding against agent-mode execution. `mc-update` should be a minimal standalone
module at `src/mc/update.py` with its own `main()` function — similar to how `mc.cli.main:main`
is the existing entry point.

**Primary recommendation:** Add `mc-update = "mc.update:main"` to `[project.scripts]` in
`pyproject.toml` and implement `src/mc/update.py` as a focused standalone module containing
the upgrade logic, post-upgrade validation, and failure recovery printing.

---

## Standard Stack

### Core (already in project dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `subprocess` | stdlib | Run `uv tool upgrade mc` and `mc --version` | Standard Python — no new deps needed |
| `sys` | stdlib | `sys.exit()`, `sys.stderr.write()` | Standard error output pattern in codebase |
| `logging` | stdlib | Debug logging | All modules use this |
| `rich` | >=14.0.0 | Already available; optional use for coloured output | Already a core dep |

### No New Dependencies Required

The upgrade command needs no new packages. All required tools (`uv`, `mc`) are external
executables invoked via `subprocess`.

**Installation:** No `pip install` needed — `rich>=14.0.0` is already a core dependency.

---

## Architecture Patterns

### Recommended Project Structure

```
src/mc/
├── update.py            # NEW: mc-update entry point module
├── cli/main.py          # Existing: mc entry point
├── runtime.py           # Reuse: agent-mode guard
├── version.py           # Reuse: get_version() for post-upgrade check
└── ...
```

### Pattern 1: Separate console_scripts Entry Point

**What:** `mc-update` is declared as its own `console_scripts` entry in `pyproject.toml`,
separate from `mc`. This is the "survives package upgrades" design — `mc-update` is a
fixed-path binary that calls into the `mc` package, so even if `mc` itself is mid-upgrade
the updater persists.

**Current entry point:**
```toml
[project.scripts]
mc = "mc.cli.main:main"
```

**Add alongside:**
```toml
[project.scripts]
mc = "mc.cli.main:main"
mc-update = "mc.update:main"
```

### Pattern 2: subprocess.run() for External Tools

**What:** The codebase's universal subprocess pattern is `subprocess.run()` with
`capture_output=True, text=True` for commands where output needs inspection, and
`check=False` when the caller handles returncode manually.

**From `platform_detect.py` (verified in codebase):**
```python
result = subprocess.run(
    ['podman', 'machine', 'list', '--format', 'json'],
    capture_output=True,
    text=True,
    check=True
)
```

**For mc-update (adapt this pattern):**
```python
# Run upgrade
result = subprocess.run(
    ['uv', 'tool', 'upgrade', 'mc'],
    capture_output=True,
    text=True,
    check=False  # Handle returncode manually to show recovery instructions
)
if result.returncode != 0:
    # Print recovery instructions
    ...

# Post-upgrade validation
verify = subprocess.run(
    ['mc', '--version'],
    capture_output=True,
    text=True,
    check=False
)
```

### Pattern 3: Agent Mode Guard (Runtime Check)

**What:** Use `runtime.should_check_for_updates()` or `runtime.is_agent_mode()` to block
`mc-update upgrade` when running inside a container. This pattern is already established
in `cli/main.py` and `runtime.py`.

**From `runtime.py` (verified):**
```python
from mc.runtime import is_agent_mode

if is_agent_mode():
    print("Updates managed via container builds. mc-update is not available in agent mode.",
          file=sys.stderr)
    sys.exit(1)
```

Alternatively, call `should_check_for_updates()` which already prints a Rich message and
returns `False` — but for a CLI command, a clean `sys.exit(1)` after the message is better
UX than a silent return.

### Pattern 4: argparse for Subcommands

**What:** The project uses `argparse`, not Click/Typer. `mc-update` should follow the
same pattern: a top-level `ArgumentParser` with a `subparsers` group for `upgrade`.

**From `cli/main.py` (verified):**
```python
parser = argparse.ArgumentParser(prog='mc-update', description='MC CLI updater')
subparsers = parser.add_subparsers(dest='command')
upgrade_parser = subparsers.add_parser('upgrade', help='Upgrade MC CLI via uv')
args = parser.parse_args()
```

### Anti-Patterns to Avoid

- **Don't import from `mc.cli.main`:** The mc-update entry point must remain independent
  so it can run even if `mc`'s CLI machinery is broken by a partial upgrade.
- **Don't use `check=True` for the upgrade subprocess:** The whole point is to catch failure
  and print recovery instructions rather than raise `CalledProcessError`.
- **Don't call `uv tool upgrade` with shell=True:** Always use list form for security
  (consistent with all other subprocess calls in the codebase).
- **Don't load config unnecessarily:** `mc-update upgrade` doesn't need `ConfigManager`
  or Salesforce tokens — keep it minimal.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding `uv` executable | Custom PATH search | `subprocess.run(['uv', ...])` — OS handles PATH | `FileNotFoundError` is the right signal if uv is missing |
| Version comparison | Custom string compare | `subprocess.run(['mc', '--version'])` — just show the output, no parsing needed | Phase 30 only requires reporting the version, not comparing it |
| Retry logic on upgrade failure | Loop with sleep | Print recovery instructions, exit 1 | Network retries are uv's responsibility |

**Key insight:** `mc-update upgrade` is a thin wrapper — it runs one command, checks the
return code, validates the result, and prints instructions. Keep it under ~80 lines.

---

## Common Pitfalls

### Pitfall 1: FileNotFoundError when uv is not on PATH

**What goes wrong:** `subprocess.run(['uv', ...])` raises `FileNotFoundError` if `uv` is
not installed or not on the current `PATH`. This surfaces as an unhandled exception.

**Why it happens:** `mc-update` is installed via `uv tool install`, so `uv` should always
be present — but defensive handling is warranted.

**How to avoid:** Wrap the subprocess call in a `try/except FileNotFoundError` and print
a specific message: `"uv not found. Install from https://docs.astral.sh/uv/"`.

**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'uv'` in
exception output.

### Pitfall 2: mc --version fails after upgrade (PATH issue)

**What goes wrong:** Post-upgrade validation runs `mc --version` but `mc` resolves to the
old binary in the current shell's `PATH` cache on some systems, or `mc` is not yet on PATH.

**Why it happens:** `uv tool upgrade` replaces the binary, but subprocess PATH lookup is
evaluated at call time — this should be fine in practice. However, if `mc` is not on PATH
at all, `FileNotFoundError` is raised.

**How to avoid:** Catch `FileNotFoundError` on the `mc --version` call separately with
a targeted message: `"mc not found on PATH after upgrade. Check: uv tool list"`.

### Pitfall 3: Upgrade "succeeds" but mc is broken

**What goes wrong:** `uv tool upgrade mc` exits 0 but the installed `mc` is corrupted or
the new version fails to start. `mc --version` would then exit non-zero.

**Why it happens:** Partial download, disk full, or dependency conflict.

**How to avoid:** The post-upgrade `mc --version` check catches this. If it fails, print
the same recovery instructions as for upgrade failure: `uv tool install --force mc`.

### Pitfall 4: Running mc-update inside a container

**What goes wrong:** User runs `mc-update upgrade` from inside an MC container session,
which would upgrade the host's `mc` installation from within the container — or fail with
permission errors.

**Why it happens:** The container has `mc` installed (agent mode), but `uv` on the PATH
inside the container may point to a different `uv` than the host.

**How to avoid:** Guard with `is_agent_mode()` check at the top of `main()`. Print a clear
message and `sys.exit(1)`.

---

## Code Examples

### Minimal mc-update module structure

```python
# src/mc/update.py
# Source: codebase patterns from cli/main.py and platform_detect.py

import argparse
import logging
import subprocess
import sys
from typing import Literal

logger = logging.getLogger(__name__)

ExitCode = Literal[0, 1]


def _run_upgrade() -> int:
    """Run uv tool upgrade mc, return exit code."""
    try:
        result = subprocess.run(
            ['uv', 'tool', 'upgrade', 'mc'],
            capture_output=False,  # Stream output directly to terminal
            text=True,
            check=False
        )
        return result.returncode
    except FileNotFoundError:
        print("Error: uv not found. Install from https://docs.astral.sh/uv/",
              file=sys.stderr)
        return 1


def _verify_mc_version() -> bool:
    """Run mc --version to confirm upgrade succeeded."""
    try:
        result = subprocess.run(
            ['mc', '--version'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print(result.stdout.strip())
            return True
        return False
    except FileNotFoundError:
        return False


def _print_recovery_instructions() -> None:
    print("", file=sys.stderr)
    print("Upgrade failed. To recover, run:", file=sys.stderr)
    print("  uv tool install --force mc", file=sys.stderr)


def upgrade() -> ExitCode:
    """Run mc-update upgrade command."""
    from mc.runtime import is_agent_mode
    if is_agent_mode():
        print("Updates managed via container builds. Run mc-update on the host.",
              file=sys.stderr)
        return 1

    print("Upgrading MC CLI...")
    rc = _run_upgrade()

    if rc != 0:
        _print_recovery_instructions()
        return 1

    print("Verifying upgrade...")
    if not _verify_mc_version():
        print("Warning: mc --version failed after upgrade.", file=sys.stderr)
        _print_recovery_instructions()
        return 1

    print("Upgrade complete.")
    return 0


def main() -> None:
    """mc-update entry point."""
    parser = argparse.ArgumentParser(
        prog='mc-update',
        description='MC CLI updater'
    )
    subparsers = parser.add_subparsers(dest='command')
    subparsers.add_parser('upgrade', help='Upgrade MC CLI via uv tool upgrade')

    args = parser.parse_args()

    if args.command == 'upgrade':
        sys.exit(upgrade())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == '__main__':
    main()
```

### pyproject.toml change

```toml
[project.scripts]
mc = "mc.cli.main:main"
mc-update = "mc.update:main"
```

### Unit test pattern (mirrors existing test_version.py, test_runtime.py)

```python
# tests/unit/test_update.py
from unittest.mock import patch, MagicMock
import subprocess
import pytest

from mc.update import upgrade, _run_upgrade, _verify_mc_version


class TestUpgrade:
    def test_upgrade_blocked_in_agent_mode(self, monkeypatch):
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        result = upgrade()
        assert result == 1

    @patch("mc.update.subprocess.run")
    def test_upgrade_success(self, mock_run, monkeypatch):
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        # First call: uv tool upgrade mc -> success
        # Second call: mc --version -> success
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout="mc 2.0.5\n")
        ]
        result = upgrade()
        assert result == 0

    @patch("mc.update.subprocess.run")
    def test_upgrade_failure_shows_recovery(self, mock_run, capsys, monkeypatch):
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_run.return_value = MagicMock(returncode=1)
        result = upgrade()
        assert result == 1
        captured = capsys.readouterr()
        assert "uv tool install --force mc" in captured.err

    @patch("mc.update.subprocess.run")
    def test_run_upgrade_filenotfound(self, mock_run, capsys):
        mock_run.side_effect = FileNotFoundError
        rc = _run_upgrade()
        assert rc == 1
        captured = capsys.readouterr()
        assert "uv not found" in captured.err
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `mc` entry point handles everything | Separate `mc-update` entry point for update ops | Phase 30 (now) | Upgrade binary survives `mc` package replacement |
| User told to run `uvx --reinstall mc-cli@latest` manually | `mc-update upgrade` wraps `uv tool upgrade mc` | Phase 30 (now) | Easier user experience, consistent verification |

**Verified notification message in version_check.py:**
```
mc v2.0.6 available. Update: uvx --reinstall mc-cli@latest
```
Phase 30 adds `mc-update upgrade` as the canonical upgrade path. The notification message
in `version_check.py` (`_display_notification`) may be updated in a later phase to advertise
`mc-update upgrade` instead of the raw `uvx` command — but that is out of scope for Phase 30.

---

## Open Questions

1. **stdout streaming vs capture during upgrade**
   - What we know: `uv tool upgrade mc` may take several seconds and prints progress to stdout
   - What's unclear: Should mc-update stream uv's output live (capture_output=False) or
     capture and re-print? Live streaming gives better UX for a long-running upgrade.
   - Recommendation: Use `capture_output=False` for the upgrade call (let uv output flow
     through), use `capture_output=True` only for the `mc --version` verification call.

2. **`uv tool upgrade` vs `uvx --reinstall mc-cli@latest`**
   - What we know: The existing notification in `version_check._display_notification()` uses
     `uvx --reinstall mc-cli@latest`. The roadmap says `mc-update upgrade` should use
     `uv tool upgrade mc`.
   - What's unclear: Whether these are equivalent for all install paths (e.g., tool installed
     with `uv tool install mc-cli` vs `uv tool install mc`).
   - Recommendation: Use `uv tool upgrade mc` as specified in requirements (UPDATE-01).
     The package name in the uv tool registry is `mc` (matching pyproject.toml `name = "mc-cli"`
     but installed as `mc`). Verify with `uv tool list` before finalizing.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `src/mc/cli/main.py` — argparse structure, entry point pattern, ExitCode type
- Codebase: `pyproject.toml` — current `[project.scripts]`, dependency list
- Codebase: `src/mc/runtime.py` — `is_agent_mode()`, `should_check_for_updates()` patterns
- Codebase: `src/mc/version_check.py` — Phase 28 infrastructure, `subprocess`-free (uses requests)
- Codebase: `src/mc/integrations/platform_detect.py` — `subprocess.run()` with `capture_output=True, text=True, check=False/True` patterns
- Codebase: `src/mc/cli/commands/other.py` — `subprocess.run()` for external tools, `print()` for user output
- Codebase: `src/mc/exceptions.py` — MCError hierarchy and exit codes
- Codebase: `tests/unit/test_cli_container_commands.py` — unit test patterns for CLI commands

### Secondary (MEDIUM confidence)

- Codebase: `src/mc/utils/errors.py` — `handle_cli_error()` pattern (not used in mc-update — too heavyweight for a standalone script)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are already in project, patterns verified in codebase
- Architecture: HIGH — entry point pattern is established, subprocess patterns verified
- Pitfalls: HIGH — derived from actual codebase patterns and known subprocess edge cases
- Test patterns: HIGH — mirror existing `test_runtime.py` and `test_version.py` patterns

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable domain — Python stdlib + uv tool upgrade semantics)
