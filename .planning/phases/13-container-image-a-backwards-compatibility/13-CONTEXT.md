# Phase 13: Container Image & Backwards Compatibility - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Build production-ready RHEL 10 container image with mc CLI and essential tooling, validate that all v1.0 commands work unchanged on the host. Scope includes image creation, tool selection, container initialization, mount configuration, and comprehensive backwards compatibility testing. Does not include new features or v1.0 behavior changes.

</domain>

<decisions>
## Implementation Decisions

### Image Contents & Tool Selection

**Tool manifest** (based on provided comprehensive list):
- Certificate Management: openssl, ssh-keygen, certtool, keytool
- Text Processing: sed, grep, wc, awk, cut, tr, sort, uniq
- File & Directory Navigation: find, ls, cd, pwd, locate
- File Viewing & Editing: less, vi, vim, nano, cat, head, tail
- Networking: curl, wget, ping, dig, nslookup, ssh, netstat, ip, nc
- Data Serialization: jq, yq, python, perl
- Archiving & Compression: zip, tar, 7zip, gzip, bzip2
- Security: openssl, gpg, chmod, chown
- System & Utilities: history, diff, man, info, top, htop, ps

**Package management:**
- Include dnf/yum in the container
- Users can install additional packages as needed for specific cases
- Runtime package installation permitted

**Python environment:**
- Python 3.11+ to match host version
- Include pip for package installation
- Minimal packages pre-installed (users install what they need)

**Text editors:**
- Both vim and nano included
- Accommodates different user preferences (power users vs simplicity)

### Container Initialization & Environment

**Shell prompt:**
- Prefixed with case number
- Format: `[case-12345678]$` to always show context
- Distinguishes container environment from host

**Environment variables:**
- Expose case metadata as environment variables
- Include: CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH
- Available for scripting and automation

**Working directory:**
- Start in `/case` (mounted workspace)
- Most common working location for case work

### Configuration & Workspace Mounting

**MC configuration access:**
- Read-only mount from host (~/.config/mc/config.toml)
- Container sees host config but cannot modify it
- Prevents accidental configuration changes

**Workspace isolation:**
- Only /case and config mounted from host
- Strict isolation - no additional host directories
- No ssh keys, credentials, or other host directories mounted

### Backwards Compatibility Validation

**Command coverage:**
- All v1.0 commands must be validated
- Comprehensive testing, not just core workflow
- Every command verified to work unchanged

**Validation approach:**
- Both automated test suite and manual validation
- Automated tests for regression detection
- Manual verification for user experience confirmation

**Workspace compatibility:**
- Pre-existing v1.0 workspaces must mount cleanly in containers
- No migration or changes required
- Existing workspace structure works without modification

### Claude's Discretion

- Startup banner design (whether to show case context before shell)
- UID/GID permission mapping strategy (strict vs flexible for specific tasks)
- Mount options beyond :U (e.g., SELinux :Z context handling)
- Container health check implementation
- Exact initialization sequence and error handling
- Tool version selection within RHEL 10 ecosystem

</decisions>

<specifics>
## Specific Ideas

- Shell prompt format explicitly requested: `[case-12345678]$` pattern
- Comprehensive tool list provided by user covers certificate management, text processing, file operations, networking, data serialization, archiving, security, and system utilities
- Match host Python version (3.11+) for consistency

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 13-container-image-a-backwards-compatibility*
*Context gathered: 2026-01-26*
