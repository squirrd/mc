# Phase 13: Container Image & Backwards Compatibility - Research

**Researched:** 2026-01-26
**Domain:** RHEL 10 container images, Python application containerization, CLI backwards compatibility
**Confidence:** HIGH

## Summary

Phase 13 focuses on building a production-ready RHEL 10 UBI container image with the mc CLI installed and essential bash tools, while ensuring all v1.0 commands continue to work unchanged on the host. Research reveals that RHEL 10 UBI standard image provides the best base for this use case, offering full dnf package manager and standard utilities. Python CLI installation in containers should use `pip install -e .` from the project root rather than building wheels. Runtime mode detection (controller vs agent) can be implemented via environment variable injection at container creation time. Backwards compatibility requires systematic testing of all existing CLI commands without using feature flags, as the phase explicitly states "no breaking changes."

**Primary recommendation:** Use `registry.access.redhat.com/ubi10/ubi:10.1` as base image, install mc CLI via `pip install --no-cache-dir -e .`, set `MC_RUNTIME_MODE=agent` environment variable in container, and test all v1.0 commands with pytest before release.

## Standard Stack

The established libraries/tools for RHEL 10 container images and Python CLI containerization:

### Core Container Image
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ubi10/ubi | 10.1 | RHEL 10 base image | Official Red Hat universal base image, freely redistributable, includes dnf package manager |
| dnf | default | Package manager | Standard RHEL package manager for installing tools, included in ubi10/ubi |
| Python 3.11+ | 3.11-3.13 | Runtime environment | Matches host Python version from pyproject.toml, available via dnf |

### Supporting Tools (From CONTEXT.md)
| Tool Category | Packages | Install Method | When to Use |
|--------------|----------|----------------|-------------|
| Certificate Management | openssl, ssh-keygen, keytool | dnf install | Pre-installed (openssl) or runtime install |
| Text Processing | sed, grep, wc, awk, cut, tr, sort, uniq | Pre-installed in UBI | Available by default |
| File & Directory Navigation | find, ls, cd, pwd, tar, gzip | Pre-installed in UBI | Available by default |
| File Viewing & Editing | less, vi, vim, nano, cat, head, tail | dnf install vim nano | Pre-install in Containerfile |
| Networking | curl, wget, ping, dig, nslookup, ssh, nc | dnf install (some pre-installed) | Pre-install common tools |
| Data Serialization | jq, yq, python, perl | dnf install jq / manual install | Runtime or pre-install |
| Archiving & Compression | zip, tar, 7zip, gzip, bzip2 | Pre-installed (tar/gzip), dnf for others | Runtime install as needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ubi10/ubi (208.5 MB) | ubi10/ubi-minimal (83.3 MB) | Minimal uses microdnf (limited capabilities), lacks pre-installed utilities like tar/gzip/vi |
| ubi10/ubi | ubi10-micro | Micro has no package manager at all, requires multi-stage builds |
| pip install -e . | pip install wheel | Editable install allows immediate code changes without rebuild, better for development-oriented container |
| Custom env var (MC_RUNTIME_MODE) | /.dockerenv file check | Environment variable is explicit, reliable, works with all runtimes (Podman/Docker) |

**Installation:**
```bash
# Base image (Containerfile FROM directive)
FROM registry.access.redhat.com/ubi10/ubi:10.1

# Essential tools
RUN dnf install -y \
    vim \
    nano \
    curl \
    wget \
    && dnf clean all

# Python and mc CLI dependencies
RUN dnf install -y python3.11 python3-pip && dnf clean all
COPY . /opt/mc
RUN pip3 install --no-cache-dir -e /opt/mc
```

## Architecture Patterns

### Recommended Project Structure
```
/
├── opt/
│   └── mc/                    # MC CLI installation (editable mode)
├── case/                      # Case workspace mount point (from host)
├── etc/
│   └── mc/
│       └── config.toml        # Read-only mount from host
└── usr/
    └── local/
        └── bin/
            └── entrypoint.sh  # Container initialization script
```

### Pattern 1: Runtime Mode Detection
**What:** Detect whether mc CLI is running in controller mode (on host) or agent mode (inside container)
**When to use:** CLI needs to conditionally enable/disable features (Podman operations only on host, not in container)
**Example:**
```python
# Source: Environment variable detection pattern (WebSearch)
import os

def get_runtime_mode() -> str:
    """Detect if running in container (agent) or on host (controller)."""
    return os.environ.get("MC_RUNTIME_MODE", "controller")

def is_agent_mode() -> bool:
    """Check if running in agent mode (inside container)."""
    return get_runtime_mode() == "agent"

# Usage in CLI code
if not is_agent_mode():
    # Only allow container operations on host
    from mc.container.manager import ContainerManager
    manager = ContainerManager()
```

### Pattern 2: Container Entrypoint with Shell Initialization
**What:** Initialize container environment and drop to interactive bash shell
**When to use:** Container needs to set up environment variables, customize prompt, display banner before shell access
**Example:**
```bash
#!/bin/bash
# Source: Docker entrypoint best practices (WebSearch)

# Set environment variables from case metadata
export CASE_NUMBER="${CASE_NUMBER}"
export CUSTOMER_NAME="${CUSTOMER_NAME}"
export WORKSPACE_PATH="/case"

# Customize shell prompt: [case-12345678]$
export PS1="[case-${CASE_NUMBER}]\$ "

# Optional: Display welcome banner
if [ -f /usr/local/bin/banner.sh ]; then
    /usr/local/bin/banner.sh
fi

# Change to workspace directory
cd /case || cd /

# Drop to interactive bash shell
# Use exec to replace entrypoint process (proper signal handling)
exec /bin/bash "$@"
```

### Pattern 3: Non-Root User for Security
**What:** Run container processes as non-root user instead of root
**When to use:** All production containers (security best practice)
**Example:**
```dockerfile
# Source: Docker non-root user best practices (WebSearch)

# Create non-root user
RUN groupadd --system mcuser && \
    useradd --system --gid mcuser --home-dir /home/mcuser --create-home mcuser

# Install mc CLI before switching user (needs root for pip install)
COPY . /opt/mc
RUN pip3 install --no-cache-dir -e /opt/mc

# Switch to non-root user
USER mcuser

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
```

### Pattern 4: Layer Optimization for Package Installation
**What:** Minimize Containerfile layers and package manager cache to reduce image size
**When to use:** Installing multiple packages via dnf/yum
**Example:**
```dockerfile
# Source: RHEL UBI layer caching best practices (WebSearch)

# BAD: Multiple RUN commands create multiple layers
RUN dnf install -y vim
RUN dnf install -y nano
RUN dnf install -y curl

# GOOD: Single RUN with cleanup
RUN dnf install -y \
    vim \
    nano \
    curl \
    wget \
    jq \
    && dnf clean all
```

### Pattern 5: Exec Form for ENTRYPOINT (Recommended)
**What:** Use exec form (JSON array) instead of shell form for ENTRYPOINT/CMD
**When to use:** Always, for proper signal handling and clean container shutdown
**Example:**
```dockerfile
# Source: Docker ENTRYPOINT best practices (WebSearch - January 2026)

# BAD: Shell form (signals not properly handled)
ENTRYPOINT /usr/local/bin/entrypoint.sh

# GOOD: Exec form (PID 1, proper signal handling)
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
```

### Anti-Patterns to Avoid
- **/.dockerenv file detection:** Deprecated and unreliable across runtimes (Docker/Podman/BuildKit), use environment variable instead
- **Editable install without --no-build-isolation:** Causes rebuild failures, always use `pip install --no-build-isolation -e .`
- **Root user in production:** Security risk, always create and switch to non-root user
- **Forgetting dnf clean all:** Leaves package manager cache in image layers, bloating image size
- **Shell form ENTRYPOINT:** Process doesn't receive signals properly, causes unclean shutdowns

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container runtime detection | Custom /.dockerenv checks | Environment variable (MC_RUNTIME_MODE=agent) | /.dockerenv doesn't exist during BuildKit builds, doesn't work in all runtimes |
| Python CLI testing in containers | Manual container runs | testcontainers-python or pytest-docker | Official pytest plugins handle container lifecycle, cleanup, fixtures |
| Package installation caching | Custom layer optimization | dnf clean all in same RUN | Standard pattern, well-documented, prevents common mistakes |
| Shell prompt customization | Complex bashrc modifications | PS1 environment variable | Simple, explicit, works across shell versions |
| Non-root user creation | Manual useradd with flags | groupadd --system + useradd --system | System users have proper UID/GID ranges, no home dir conflicts |

**Key insight:** Container ecosystems are mature with established patterns. The RHEL/UBI documentation, Docker/Podman best practices guides, and Python packaging standards provide battle-tested solutions. Custom approaches introduce subtle bugs (signal handling, permission mapping, cache bloat) that are hard to debug.

## Common Pitfalls

### Pitfall 1: Using UBI Minimal and Missing Essential Tools
**What goes wrong:** ubi-minimal (83.3 MB) uses microdnf instead of dnf, lacks pre-installed utilities like tar/gzip/vi, and has a limited package set
**Why it happens:** Developers choose minimal image for size savings without understanding tradeoffs
**How to avoid:** Use ubi10/ubi:10.1 (208.5 MB) for comprehensive tooling and full dnf capabilities. Size difference is negligible for development containers.
**Warning signs:** Commands like `tar`, `vi`, or `gzip` fail with "command not found" in container

### Pitfall 2: jq and Other Tools Not in Default UBI Repositories
**What goes wrong:** Common tools like `jq` may not be available via `dnf install jq` from UBI repositories
**Why it happens:** UBI repositories are curated subset of RHEL, not all EPEL packages included
**How to avoid:** Test all required tools during Containerfile build. For missing tools, either: (1) allow runtime installation with `dnf install -y`, (2) download pre-built binaries from GitHub releases, or (3) document for users to install as needed
**Warning signs:** `dnf install jq` fails with "No package jq available"

### Pitfall 3: Editable Install Breaks Without --no-build-isolation
**What goes wrong:** `pip install -e .` in container succeeds at build time but fails when importing the package at runtime
**Why it happens:** Build dependencies aren't available in runtime environment when using build isolation
**How to avoid:** Use `pip install --no-build-isolation --no-cache-dir -e .` when installing in editable mode
**Warning signs:** Container builds successfully but `import mc` fails with build-related errors

### Pitfall 4: Python Version Mismatch Between Host and Container
**What goes wrong:** Host uses Python 3.13, container installs Python 3.9, causing dependency incompatibilities
**Why it happens:** Default Python in UBI may be older than host version
**How to avoid:** Explicitly install matching Python version: `dnf install -y python3.11` or use Python runtime UBI images (ubi10/python-312-minimal)
**Warning signs:** Type hints fail, syntax errors on features added in newer Python versions

### Pitfall 5: Shell Form ENTRYPOINT Prevents Clean Shutdown
**What goes wrong:** Container ignores SIGTERM/SIGINT signals, requires SIGKILL for shutdown (10-second timeout)
**Why it happens:** Shell form wraps command in `/bin/sh -c`, shell becomes PID 1 but doesn't forward signals
**How to avoid:** Always use exec form: `ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]` instead of `ENTRYPOINT /usr/local/bin/entrypoint.sh`
**Warning signs:** `podman stop` takes 10+ seconds (waiting for SIGKILL timeout)

### Pitfall 6: Forgetting to Clean Package Manager Cache
**What goes wrong:** Container image size balloons by 50-100 MB due to cached RPM packages
**Why it happens:** dnf caches downloaded packages by default, cache persists in image layer
**How to avoid:** Always chain `&& dnf clean all` in same RUN command as `dnf install`
**Warning signs:** Final image size is 300+ MB instead of expected 208 MB

### Pitfall 7: Backwards Compatibility Testing Only Covers "Happy Path"
**What goes wrong:** Edge cases and error conditions break in v2.0 even though core workflow works
**Why it happens:** Manual testing focuses on successful operations, automated tests needed for comprehensive coverage
**How to avoid:** Run full pytest suite against v1.0 commands on host before shipping. Test both success and failure scenarios (invalid case numbers, network failures, missing files).
**Warning signs:** Users report regressions in error handling or edge cases that weren't manually tested

### Pitfall 8: UID/GID Mapping Issues with Mounted Workspace
**What goes wrong:** Files created in container are owned by root:root on host, not host user
**Why it happens:** Container runs as root, volume mount doesn't map UIDs without userns configuration
**How to avoid:** Already addressed in Phase 11 with `--userns=keep-id` and `:U` mount suffix. Ensure container image doesn't override this by running as root.
**Warning signs:** `ls -la /case` shows root:root ownership for files created in container

## Code Examples

Verified patterns from official sources:

### Containerfile for RHEL 10 UBI with MC CLI
```dockerfile
# Source: RHEL 10 UBI official catalog + Docker best practices
FROM registry.access.redhat.com/ubi10/ubi:10.1

# Install essential tools in single layer with cache cleanup
RUN dnf install -y \
    python3.11 \
    python3-pip \
    vim \
    nano \
    curl \
    wget \
    openssl \
    && dnf clean all

# Create non-root user for security
RUN groupadd --system mcuser && \
    useradd --system --gid mcuser --home-dir /home/mcuser --create-home mcuser

# Install mc CLI in editable mode (must be before USER switch)
COPY --chown=mcuser:mcuser . /opt/mc
RUN pip3 install --no-cache-dir --no-build-isolation -e /opt/mc

# Set runtime mode environment variable
ENV MC_RUNTIME_MODE=agent

# Create workspace mount point
RUN mkdir -p /case && chown mcuser:mcuser /case

# Copy entrypoint script
COPY --chown=mcuser:mcuser scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Switch to non-root user
USER mcuser

# Set working directory to case workspace
WORKDIR /case

# Use exec form for proper signal handling
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
```

### Container Entrypoint Script with Environment Setup
```bash
#!/bin/bash
# Source: Docker entrypoint best practices (WebSearch)

# Exit on error, undefined variables
set -euo pipefail

# Set case-specific environment variables (injected by container creation)
export CASE_NUMBER="${CASE_NUMBER:-unknown}"
export CUSTOMER_NAME="${CUSTOMER_NAME:-unknown}"
export WORKSPACE_PATH="/case"

# Customize shell prompt: [case-12345678]$
export PS1="[case-${CASE_NUMBER}]\$ "

# Change to workspace directory
cd "${WORKSPACE_PATH}" || {
    echo "Warning: Could not change to workspace directory" >&2
    cd /
}

# Display welcome banner if present
if [ -f /usr/local/bin/banner.sh ]; then
    /usr/local/bin/banner.sh
fi

# Execute command (default: /bin/bash)
# Use exec to replace entrypoint process (PID 1 for proper signal handling)
exec "$@"
```

### Runtime Mode Detection in Python CLI
```python
# Source: Environment variable detection pattern
import os
from typing import Literal

RuntimeMode = Literal["controller", "agent"]

def get_runtime_mode() -> RuntimeMode:
    """
    Detect whether mc CLI is running in controller or agent mode.

    Controller mode: Running on host, has access to Podman operations
    Agent mode: Running inside container, limited to workspace operations

    Returns:
        "controller" if running on host, "agent" if running in container
    """
    mode = os.environ.get("MC_RUNTIME_MODE", "controller")
    if mode not in ("controller", "agent"):
        # Default to controller for safety
        return "controller"
    return mode  # type: ignore

def is_agent_mode() -> bool:
    """Check if CLI is running in agent mode (inside container)."""
    return get_runtime_mode() == "agent"

def is_controller_mode() -> bool:
    """Check if CLI is running in controller mode (on host)."""
    return get_runtime_mode() == "controller"

# Usage example in CLI code
if is_controller_mode():
    # Only import and use container operations on host
    from mc.container.manager import ContainerManager
    manager = ContainerManager()
else:
    # Inside container, don't attempt Podman operations
    print("Container operations not available in agent mode")
```

### Backwards Compatibility Testing with Pytest
```python
# Source: pytest argparse testing patterns (WebSearch)
import subprocess
import pytest
from typing import List

def run_cli_command(args: List[str]) -> subprocess.CompletedProcess:
    """Run mc CLI command and capture result."""
    result = subprocess.run(
        ["mc"] + args,
        capture_output=True,
        text=True,
        timeout=30
    )
    return result

class TestBackwardsCompatibility:
    """Test all v1.0 commands work unchanged on host."""

    def test_attach_command_exists(self):
        """mc attach <case_number> command should still work."""
        result = run_cli_command(["attach", "--help"])
        assert result.returncode == 0
        assert "Download attachments" in result.stdout

    def test_check_command_exists(self):
        """mc check <case_number> command should still work."""
        result = run_cli_command(["check", "--help"])
        assert result.returncode == 0
        assert "Check the state of a workspace" in result.stdout

    def test_create_command_exists(self):
        """mc create <case_number> command should still work."""
        result = run_cli_command(["create", "--help"])
        assert result.returncode == 0
        assert "Create a workspace" in result.stdout

    def test_case_comments_command_exists(self):
        """mc case-comments <case_number> command should still work."""
        result = run_cli_command(["case-comments", "--help"])
        assert result.returncode == 0

    def test_ls_command_exists(self):
        """mc ls <uid> command should still work."""
        result = run_cli_command(["ls", "--help"])
        assert result.returncode == 0
        assert "Search for a user in LDAP" in result.stdout

    def test_go_command_exists(self):
        """mc go <case_number> command should still work."""
        result = run_cli_command(["go", "--help"])
        assert result.returncode == 0
```

### Building and Tagging Container Image with Podman
```bash
# Source: Podman build best practices (WebSearch)

# Build image from Containerfile (or Dockerfile - both work)
podman build -t mc-rhel10:latest -f Containerfile .

# Tag with version for release
podman build -t mc-rhel10:2.0.0 -f Containerfile .

# Tag with both registry paths for distribution
podman tag mc-rhel10:latest localhost/mc-rhel10:latest
podman tag mc-rhel10:2.0.0 localhost/mc-rhel10:2.0.0

# Push to registry (if needed)
# podman push localhost/mc-rhel10:2.0.0 registry.example.com/mc-rhel10:2.0.0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Dockerfile only | Containerfile preferred (Dockerfile still works) | OCI compliance era | Podman/Buildah prioritize Containerfile, fall back to Dockerfile |
| /.dockerenv file check | Environment variable injection | BuildKit introduction (2020+) | /.dockerenv unreliable during builds and across runtimes |
| Shell form ENTRYPOINT | Exec form ENTRYPOINT (JSON array) | Docker best practices 2018+ | Proper signal handling, PID 1 management |
| pip install wheel | pip install -e . for dev containers | PEP 660 (2021) | Editable installs work with pyproject.toml-only projects |
| Manual user creation | useradd --system for container users | Security hardening 2020+ | System users have appropriate UID ranges, no conflicts |
| TLS 1.0/1.1 for registry access | TLS 1.2+ required | January 15, 2026 | registry.redhat.io dropped TLS 1.0/1.1 support |

**Deprecated/outdated:**
- **.dockerenv file detection:** Unreliable across BuildKit and Podman, doesn't exist during builds
- **optparse:** Replaced by argparse in Python 3.2+, backwards compatibility with optparse unreasonably difficult
- **UBI 8 images:** RHEL 8 lifecycle approaching end, use RHEL 10 UBI for new projects
- **python:alpine images for RHEL projects:** Use ubi10/python-* for Red Hat ecosystem consistency

## Open Questions

Things that couldn't be fully resolved:

1. **Which tools from comprehensive tool list are NOT in default UBI repositories?**
   - What we know: jq may not be available via dnf in UBI repos (discussion found but not confirmed for UBI 10), openssl is pre-installed
   - What's unclear: Complete inventory of which tools from user's list (keytool, certtool, yq, htop, etc.) are available vs need manual installation
   - Recommendation: Build test Containerfile that attempts `dnf install` of all tools, document which fail, provide installation instructions or deferment to runtime install

2. **Should container image include Python runtime base (ubi10/python-312-minimal) or install Python on standard UBI?**
   - What we know: Both approaches work, ubi10/python-312-minimal exists and is smaller, standard UBI + dnf install python3.11 is more flexible
   - What's unclear: Performance/size tradeoff, whether Python runtime images include pip by default
   - Recommendation: Start with standard UBI + dnf install python3.11 for flexibility (matches host Python version), can optimize to runtime image later

3. **Do we need multi-stage build for smaller final image?**
   - What we know: Multi-stage builds copy only runtime artifacts from builder stage, reducing final image size
   - What's unclear: Whether size optimization is needed for this use case (development container, not production app)
   - Recommendation: Single-stage build initially (simpler, faster iteration), revisit if image size becomes problematic (>500 MB)

4. **How to handle container image versioning and updates?**
   - What we know: Podman supports tagging with versions, can push to registries
   - What's unclear: Versioning strategy (tag with mc CLI version? separate image version?), update mechanism for existing containers
   - Recommendation: Tag image with mc CLI version (e.g., mc-rhel10:2.0.0), document image rebuild process, plan for image updates in future phase

## Sources

### Primary (HIGH confidence)
- [Red Hat UBI 10 Standard Image Catalog](https://catalog.redhat.com/en/software/containers/ubi10/ubi/66f2b46b122803e4937d11ae) - Image specifications, size, registry URLs
- [Red Hat UBI 10 Minimal Image Catalog](https://catalog.redhat.com/en/software/containers/ubi10/ubi-minimal/66f1504a379b9c2cf23e145c) - Minimal variant specifications
- [UBI Registry URLs and Licensing](https://access.redhat.com/articles/4238681) - Official registry URLs, licensing model
- [RHEL UBI Differences Official Docs](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_types-of-container-images_building-running-and-managing-containers) - UBI minimal vs standard comparison
- [pip install Documentation](https://pip.pypa.io/en/stable/cli/pip_install/) - Editable install options
- [setuptools Development Mode](https://setuptools.pypa.io/en/latest/userguide/development_mode.html) - Editable installs with pyproject.toml
- [Podman Build Documentation](https://docs.podman.io/en/latest/markdown/podman-build.1.html) - Build command reference
- [Podman Volume Mount Options](https://docs.podman.io/en/v4.3/markdown/options/volume.html) - Read-only mount syntax
- [pytest Backwards Compatibility Policy](https://docs.pytest.org/en/stable/backwards-compatibility.html) - Python deprecation policy patterns

### Secondary (MEDIUM confidence)
- [Docker Entrypoint vs CMD (January 2026)](https://oneuptime.com/blog/post/2026-01-16-docker-entrypoint-vs-cmd/view) - Exec form best practices
- [Python Container Best Practices (Snyk)](https://snyk.io/blog/best-practices-containerizing-python-docker/) - Layer optimization, non-root users
- [Containerfile vs Dockerfile Discussion](https://github.com/containers/buildah/discussions/3170) - OCI naming conventions
- [Podman vs Docker 2026 Comparison](https://last9.io/blog/podman-vs-docker/) - Containerfile priority over Dockerfile
- [Run Python as Non-Root User](https://medium.com/@DahlitzF/run-python-applications-as-non-root-user-in-docker-containers-by-example-cba46a0ff384) - Security best practices
- [Testcontainers Python Guide](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/) - Container integration testing
- [pytest-docker Plugin](https://github.com/avast/pytest-docker) - Docker integration for pytest
- [RHEL UBI Layer Caching](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_adding-software-to-a-ubi-container_building-running-and-managing-containers) - dnf clean all pattern

### Tertiary (LOW confidence)
- [jq Installation Discussion](https://access.redhat.com/discussions/4134661) - jq availability in UBI repositories (not confirmed for UBI 10)
- [Container Detection via Environment Variables](https://www.baeldung.com/linux/is-process-running-inside-container) - Multiple detection methods
- [/.dockerenv Deprecated Discussion](https://github.com/moby/buildkit/issues/4503) - BuildKit compatibility issues
- [Bash Prompt Customization](https://gist.github.com/scmx/242caa249b0ea343e2588adea14479e6) - Docker container PS1 example

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Red Hat catalog and documentation provide authoritative image specifications
- Architecture: HIGH - Docker/Podman best practices well-established, entrypoint patterns verified across multiple sources
- Pitfalls: MEDIUM - Based on community discussions and common issues, some UBI 10 specifics extrapolated from UBI 9 docs
- Code examples: HIGH - Verified against official documentation and recent best practices guides

**Research date:** 2026-01-26
**Valid until:** 30 days (RHEL 10 is new, monitor for updates to UBI image capabilities and package availability)
