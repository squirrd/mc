# Phase 27: Runtime Mode Detection - Research

**Researched:** 2026-02-19
**Domain:** Container detection and runtime mode awareness for auto-update control
**Confidence:** HIGH

## Summary

Runtime mode detection is a critical safety mechanism to prevent auto-update functionality from executing inside containerized environments where updates should be managed via container image builds, not in-place package upgrades. The MC CLI project already has a working runtime detection system based on the `MC_RUNTIME_MODE` environment variable set in the Containerfile, which is the recommended primary detection method.

Research confirms that environment variable-based detection is the standard industry approach for container-aware applications, particularly when the application controls both the container build and the host CLI. Multiple fallback detection methods exist (/.dockerenv, /run/.containerenv, /proc/self/cgroup), but these are primarily needed when detecting third-party container environments. For MC CLI's use case—where we control the Containerfile and set MC_RUNTIME_MODE=agent explicitly—the existing environment variable approach is sufficient and correct.

**Primary recommendation:** Extend existing runtime.py module to integrate with auto-update logic, add defensive fallback detection for robustness, and ensure informational messages guide users when running in agent mode.

## Standard Stack

The established libraries/tools for container detection and runtime mode handling:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (os, pathlib) | 3.11+ | Environment variable and file system access | No external dependencies needed for detection |
| mc.runtime (existing) | Current | Runtime mode detection via MC_RUNTIME_MODE | Already implemented and tested (tests/unit/test_runtime.py) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Rich | 14.0.0+ (existing) | Informational banners for agent mode | Already in use for MC CLI output |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Environment variable | File detection (/.dockerenv, /run/.containerenv) | Environment variable is more explicit and portable; file detection needed only for fallback |
| Environment variable | cgroups parsing (/proc/self/cgroup) | cgroups detection is fragile across v1/v2 transition; environment variable is simpler |

**Installation:**
No new dependencies required. All detection methods use Python stdlib or existing project dependencies.

## Architecture Patterns

### Recommended Integration Pattern
```
Auto-update flow:
1. Check runtime mode via runtime.is_agent_mode()
2. If agent mode: Skip update, show informational message
3. If controller mode: Proceed with version check and update logic
```

### Pattern 1: Primary Detection (Environment Variable)
**What:** Read MC_RUNTIME_MODE environment variable set by Containerfile
**When to use:** Primary detection method (already implemented)
**Example:**
```python
# Source: /Users/dsquirre/Repos/mc/src/mc/runtime.py
import os
from typing import Literal

RuntimeMode = Literal["controller", "agent"]

def get_runtime_mode() -> RuntimeMode:
    """Get current runtime mode (controller or agent).

    Returns "controller" if running on host, "agent" if running in container.
    Invalid values default to "controller" for safety.
    """
    mode = os.environ.get("MC_RUNTIME_MODE", "controller")

    if mode not in ("controller", "agent"):
        return "controller"  # Safer default

    return mode  # type: ignore[return-value]

def is_agent_mode() -> bool:
    """Check if running in agent mode (inside container)."""
    return get_runtime_mode() == "agent"

def is_controller_mode() -> bool:
    """Check if running in controller mode (on host)."""
    return get_runtime_mode() == "controller"
```

### Pattern 2: Fallback Detection (File-based)
**What:** Check for container indicator files when environment variable not set
**When to use:** Defensive fallback for edge cases (manual container runs, third-party containers)
**Example:**
```python
# Source: Container detection research (Podman/Docker documentation)
from pathlib import Path

def detect_container_via_files() -> bool:
    """Fallback container detection using filesystem indicators.

    Checks for:
    - /run/.containerenv (Podman)
    - /.dockerenv (Docker)

    Returns True if any indicator file exists.
    """
    return (
        Path("/run/.containerenv").exists() or
        Path("/.containerenv").exists() or
        Path("/.dockerenv").exists()
    )
```

### Pattern 3: Informational Messaging
**What:** Display Rich banner when auto-update disabled due to agent mode
**When to use:** When version check detects update available but agent mode prevents it
**Example:**
```python
# Conceptual pattern using existing Rich library
from rich.console import Console

console = Console(stderr=True)

def show_agent_mode_message() -> None:
    """Display informational banner for container mode."""
    console.print(
        "[yellow]ℹ Updates managed via container builds[/yellow]",
        style="bold"
    )
```

### Pattern 4: Layered Detection (Defense in Depth)
**What:** Combine environment variable (primary) with file detection (fallback)
**When to use:** Production auto-update guard to prevent container corruption
**Example:**
```python
def is_running_in_container() -> bool:
    """Detect if running inside container using layered approach.

    Priority:
    1. MC_RUNTIME_MODE environment variable (explicit, set by our Containerfile)
    2. Container indicator files (defensive fallback)

    Returns True if running in any container context.
    """
    # Primary: Check explicit environment variable
    if os.environ.get("MC_RUNTIME_MODE") == "agent":
        return True

    # Fallback: Check filesystem indicators
    return detect_container_via_files()
```

### Anti-Patterns to Avoid
- **Parsing /proc/self/cgroup:** Fragile across cgroups v1→v2 migration, format changes in Linux 6.12+ (JDK-8347811, JDK-8349527). Only use if absolutely necessary for third-party container detection.
- **Case-insensitive environment variable checks:** MC_RUNTIME_MODE must be exactly "agent" or "controller" (test_case_sensitive_mode_detection validates this)
- **Assuming /.dockerenv always exists:** File not created in all container runtimes (buildah shell, some CI environments)
- **Ignoring environment variable in favor of file detection:** Environment variable is more explicit and reliable when you control the container build

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container detection | Custom cgroups parser | Environment variable + file fallback | cgroups v1→v2 migration broke many parsers (Linux 6.12+); /proc/cgroups deprecated |
| Runtime mode tracking | Global variable or module state | os.environ with validation | Environment inherits to child processes; no mutable state needed |
| Informational messaging | print() statements | Rich Console (already in stack) | Consistent styling; stderr output; no TTY detection needed |

**Key insight:** Container detection is a solved problem with well-established patterns. The existing runtime.py implementation follows best practices. Don't reinvent multi-method detection unless supporting third-party container environments.

## Common Pitfalls

### Pitfall 1: Relying Solely on File-based Detection
**What goes wrong:** Container indicator files may not exist in all environments (buildah shell doesn't create /.dockerenv or /run/.containerenv - GitHub containers/buildah#1843)
**Why it happens:** Different container runtimes have different conventions; not all create indicator files
**How to avoid:** Use environment variable as primary method (explicit contract); file detection only as fallback
**Warning signs:** Auto-update running inside containers, corrupt container state, "uv tool upgrade" failing in agent mode

### Pitfall 2: cgroups v1/v2 Transition Issues
**What goes wrong:** Parsing /proc/self/cgroup breaks when Linux kernel or container runtime updates from cgroups v1 to v2
**Why it happens:** Format changed from multiple lines with hierarchy numbers to single line "0::$PATH"; /proc/cgroups deprecated in v2; Linux 6.12+ broke JVM container detection
**How to avoid:** Don't parse cgroups unless absolutely necessary; prefer explicit environment variables
**Warning signs:** Container detection working on dev machines but failing in production; behavior changes after kernel updates

### Pitfall 3: Forgetting to Set Environment Variable in Containerfile
**What goes wrong:** Container builds without MC_RUNTIME_MODE=agent, detection fails, auto-update runs inside container
**Why it happens:** Easy to forget ENV directive when modifying Containerfile
**How to avoid:** Integration test that verifies MC_RUNTIME_MODE=agent inside running container; CI check for ENV directive presence
**Warning signs:** Auto-update attempts inside container; container tests passing but production containers updating incorrectly

### Pitfall 4: Case Sensitivity in Mode Detection
**What goes wrong:** Setting MC_RUNTIME_MODE=AGENT (uppercase) causes detection to fail, defaults to controller mode
**Why it happens:** String comparison is case-sensitive; validation doesn't normalize case
**How to avoid:** Document exact values ("agent" and "controller") in Containerfile comments; test validates case sensitivity
**Warning signs:** Container mode not detected despite ENV directive; auto-update running when it shouldn't

### Pitfall 5: Not Testing Fallback Detection
**What goes wrong:** Primary detection works but fallback never tested; fails when needed most (manual container runs)
**Why it happens:** Happy path testing only validates environment variable; edge cases ignored
**How to avoid:** Unit tests for each detection method independently; integration test for fallback chain
**Warning signs:** Detection works in normal containers but fails in manual "podman run" commands

## Code Examples

Verified patterns from official sources and existing codebase:

### Container Environment Variable (Containerfile)
```dockerfile
# Source: /Users/dsquirre/Repos/mc/container/Containerfile line 183
# Set runtime mode to identify agent mode (inside container)
ENV MC_RUNTIME_MODE=agent
```

### Runtime Mode Detection (Existing Implementation)
```python
# Source: /Users/dsquirre/Repos/mc/src/mc/runtime.py
import os
from typing import Literal

RuntimeMode = Literal["controller", "agent"]

def get_runtime_mode() -> RuntimeMode:
    """Get current runtime mode (controller or agent).

    The runtime mode is determined by the MC_RUNTIME_MODE environment variable:
    - "agent": Running inside a container (set by container entrypoint)
    - "controller": Running on host (default when variable not set)

    Invalid values default to "controller" for safety (host mode is safer default).
    """
    mode = os.environ.get("MC_RUNTIME_MODE", "controller")

    # Validate mode value - must be exactly "controller" or "agent"
    if mode not in ("controller", "agent"):
        # Invalid value defaults to controller (safer default)
        return "controller"

    return mode  # type: ignore[return-value]

def is_agent_mode() -> bool:
    """Check if running in agent mode (inside container)."""
    return get_runtime_mode() == "agent"

def is_controller_mode() -> bool:
    """Check if running in controller mode (on host)."""
    return get_runtime_mode() == "controller"
```

### Auto-Update Guard Pattern
```python
# Conceptual pattern for Phase 28 (version check infrastructure)
from mc.runtime import is_agent_mode
from rich.console import Console

console = Console(stderr=True)

def should_check_for_updates() -> bool:
    """Determine if version checking should proceed.

    Returns False if running in agent mode (container).
    """
    if is_agent_mode():
        console.print(
            "[yellow]ℹ Updates managed via container builds[/yellow]",
            style="bold"
        )
        return False

    return True

# Usage in version check flow
if should_check_for_updates():
    # Proceed with GitHub API version check
    check_github_releases()
```

### Defensive Fallback Detection
```python
# Optional enhancement for robustness
from pathlib import Path
import os

def is_running_in_container() -> bool:
    """Detect container with layered approach (primary + fallback).

    Priority:
    1. MC_RUNTIME_MODE environment variable (explicit)
    2. Container indicator files (defensive fallback)
    """
    # Primary: explicit environment variable
    mode = os.environ.get("MC_RUNTIME_MODE")
    if mode == "agent":
        return True

    # Fallback: filesystem indicators (Podman, Docker)
    container_files = [
        Path("/run/.containerenv"),
        Path("/.containerenv"),
        Path("/.dockerenv")
    ]

    return any(f.exists() for f in container_files)
```

### Testing Runtime Mode Detection
```python
# Source: /Users/dsquirre/Repos/mc/tests/unit/test_runtime.py
import pytest
from mc.runtime import get_runtime_mode, is_agent_mode, is_controller_mode

class TestGetRuntimeMode:
    def test_default_mode_is_controller_when_env_var_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that default mode is 'controller' when MC_RUNTIME_MODE not set."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        mode = get_runtime_mode()

        assert mode == "controller"

    def test_mode_is_agent_when_env_var_set_to_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that mode is 'agent' when MC_RUNTIME_MODE=agent."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        mode = get_runtime_mode()

        assert mode == "agent"

    def test_invalid_mode_value_defaults_to_controller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalid MC_RUNTIME_MODE values default to 'controller'."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "invalid")

        mode = get_runtime_mode()

        assert mode == "controller"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parse /proc/cgroups for container detection | Check /sys/fs/cgroup/cgroup.subtree_control | Linux 6.12 (2024), OpenJDK JDK-8347811 | /proc/cgroups meaningless for cgroups v2; broke container detection in JVM |
| cgroups v1 multi-hierarchy | cgroups v2 unified hierarchy | RHEL 8+, Kubernetes 1.31 (maintenance mode for v1) | /proc/self/cgroup format changed from multiple lines to "0::$PATH" |
| File-based detection only | Environment variable + file fallback | 2020s container-aware apps | More explicit contract; survives buildah and other runtimes |
| /.dockerenv only | /run/.containerenv (Podman) + /.dockerenv (Docker) | Podman v1.0+ (2019) | Podman-specific indicator file for better detection |

**Deprecated/outdated:**
- Parsing /proc/cgroups: Meaningless for cgroups v2, deprecated by kernel developers
- Relying on /.dockerenv alone: Doesn't exist in all container runtimes (buildah, some CI)
- cgroups v1 detection code: RHEL 8+ uses v2, Kubernetes 1.31 moved v1 to maintenance mode
- Assuming /proc/self/cgroup format is stable: Broken by Linux 6.12 kernel changes

## Open Questions

Things that couldn't be fully resolved:

1. **Should fallback detection be implemented in Phase 27 or deferred?**
   - What we know: Environment variable detection is already working and sufficient for MC CLI's controlled environment
   - What's unclear: Whether edge cases (manual podman runs, third-party containers) justify additional complexity now
   - Recommendation: Implement defensive fallback detection in Phase 27 for robustness, but keep it simple (file checks only, no cgroups parsing)

2. **How should informational messages be displayed?**
   - What we know: Rich Console used throughout MC CLI; stderr is correct output stream
   - What's unclear: Should message show every time agent mode blocks an operation, or cache to prevent spam?
   - Recommendation: Display message when auto-update check would have run but is blocked by agent mode; no caching needed (hourly throttle already prevents spam)

3. **Should runtime mode detection be logged?**
   - What we know: MC CLI has structured logging with sensitive data redaction
   - What's unclear: Is runtime mode detection worth logging for debugging container issues?
   - Recommendation: Log at DEBUG level when mode is determined; helps troubleshoot auto-update issues in production

## Sources

### Primary (HIGH confidence)
- MC CLI existing runtime.py implementation - /Users/dsquirre/Repos/mc/src/mc/runtime.py
- MC CLI Containerfile ENV directive - /Users/dsquirre/Repos/mc/container/Containerfile line 183
- MC CLI runtime tests - /Users/dsquirre/Repos/mc/tests/unit/test_runtime.py
- Podman documentation on .containerenv - https://docs.podman.io/en/v5.1.1/markdown/podman-run.1.html
- Kubernetes cgroup v2 documentation - https://kubernetes.io/docs/concepts/architecture/cgroups/

### Secondary (MEDIUM confidence)
- GitHub container detection gist - https://gist.github.com/anantkamath/623ce7f5432680749e087cf8cfba9b69
- OpenJDK cgroups v2 issues - https://bugs.openjdk.org/browse/JDK-8347811, https://bugs.openjdk.org/browse/JDK-8230305
- Buildah .containerenv issue - https://github.com/containers/buildah/issues/1843
- Docker environment variables documentation - https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/
- Podman vs Docker container detection discussion - https://lists.podman.io/archives/list/podman@lists.podman.io/thread/6D72V37DEP26BNQDZHRCGHMZELHKN24A/

### Tertiary (LOW confidence - WebSearch only)
- Container security best practices 2026 - https://www.ox.security/blog/container-security-best-practices/
- Python Docker best practices - https://testdriven.io/blog/docker-best-practices/
- Container detection methods overview - https://www.iditect.com/faq/python/how-to-detect-if-one-is-running-within-a-docker-container-within-python.html

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Existing implementation verified, no external dependencies needed
- Architecture: HIGH - Patterns verified in existing codebase and official Podman/Docker docs
- Pitfalls: HIGH - Based on real-world issues (OpenJDK bugs, buildah GitHub issues, cgroups v2 migration)

**Research date:** 2026-02-19
**Valid until:** 60 days (stable container detection methods, slow-moving ecosystem)
