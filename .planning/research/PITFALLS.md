# Pitfalls Research: Container Orchestration with Salesforce Integration

**Domain:** Rootless Podman CLI orchestrator with external API integration
**Researched:** 2026-01-26
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: UID/GID Mapping Confusion in Volume Mounts

**What goes wrong:**
Container creates files in mounted workspace directories that appear owned by unexpected UIDs on the host (e.g., UID 100025 instead of the user's UID 1000), causing permission denied errors when the host user tries to access files created by the container.

**Why it happens:**
Rootless Podman maps the container's root user (UID 0) to the host user's UID, but other container UIDs are mapped to subuids defined in `/etc/subuid`. If a container process runs as UID 26, it appears as UID 100025 on the host. Developers assume container UID 0 = host UID 0, or that mounted volumes preserve host permissions.

**How to avoid:**
- Use `podman run --userns=keep-id` to map the host user's UID directly into the container
- Add `:U` suffix to volume mounts (e.g., `-v ~/cases/12345678:/workspace:U`) to automatically recursively chown the volume to match the container's user
- Document clearly which user (root vs. non-root) runs inside the container
- Test file creation/modification from both container and host before finalizing

**Warning signs:**
- `ls -la` shows unexpected high UIDs (100000+) on workspace files
- Permission denied errors when accessing files created by container
- Files owned by "nobody" or unmapped UIDs
- chown commands fail inside containers

**Phase to address:**
Phase 1 (Container Architecture & Podman Integration) - core volume mounting strategy must be established during initial implementation to prevent architectural rework later.

---

### Pitfall 2: Pasta Networking Breaks Inter-Container Communication

**What goes wrong:**
On Podman 5.0+, containers cannot communicate with each other or with services on the host's primary IP address because pasta (the new default networking) copies the host's IP, preventing connections to that IP from containers.

**Why it happens:**
Podman 5.0 switched from slirp4netns to pasta as the default rootless networking backend. Pasta improves performance but has the side effect of copying the main interface's IP address. If the host only has one network interface, inter-container networking fails without explicit pasta configuration.

**How to avoid:**
- Explicitly test container-to-container communication during development
- For MC's use case (single containers per case), document that cross-case container communication is not supported
- If inter-container communication becomes required, configure pasta explicitly: `--network pasta:--config-net` or fall back to slirp4netns with `--network slirp4netns`
- Test on both single-NIC and multi-NIC systems

**Warning signs:**
- Containers can reach the internet but not each other
- `podman exec <container> curl http://<host-ip>:<port>` times out
- Works on developer's multi-NIC Linux workstation but fails on production single-NIC system
- Network connectivity issues that don't appear in rootful Podman

**Phase to address:**
Phase 1 (Container Architecture & Podman Integration) - network architecture decisions impact container isolation model and must be validated early.

---

### Pitfall 3: Salesforce API Token Expiration During Long-Running Operations

**What goes wrong:**
Container is created successfully with case metadata, but 60+ minutes later when the user lists containers or attaches to one, the CLI fails with authentication errors because the Salesforce access token expired (typically 2-hour lifetime). Case metadata becomes stale or inaccessible.

**Why it happens:**
Salesforce access tokens expire after a fixed duration (commonly 2 hours, configurable). Long-lived operations (container running overnight, user switches contexts) assume tokens remain valid indefinitely. The CLI doesn't detect token expiration until attempting API calls, leading to confusing failures during routine operations.

**How to avoid:**
- Cache access tokens with expiration metadata (using `expires_in` from OAuth response)
- Check token expiration before every Salesforce API call, refresh proactively 5 minutes before expiry
- Implement automatic refresh using stored refresh tokens (store in secure local cache)
- Provide clear error messages distinguishing "auth expired, refreshing..." from "re-authentication required"
- Handle refresh token expiration (max 5 concurrent tokens per user per connected app) by prompting re-authentication
- Store container metadata locally (case number, subject, priority) independent of live API access

**Warning signs:**
- Intermittent "invalid_grant" or "Session expired" errors
- Features work immediately after login but fail hours later
- Token refresh requests themselves return 401
- Error messages mention "expired access token"

**Phase to address:**
Phase 2 (Salesforce Integration & Case Resolution) - token lifecycle management is foundational to reliable API integration and must be robust before metadata features are built on top.

---

### Pitfall 4: Orphaned Containers from Unclean Shutdowns

**What goes wrong:**
User kills the CLI with Ctrl+C or experiences system crash during container operations, leaving containers running without metadata tracking. `mc list` doesn't show them, but `podman ps` does. Workspace directories exist but aren't associated with containers. System accumulates ghost containers consuming resources.

**Why it happens:**
Container creation and metadata storage are not atomic operations. If the CLI creates a Podman container but crashes before writing metadata (label, state file, database entry), the container exists but is invisible to MC. Reverse scenario: metadata exists but container was removed externally via `podman rm`.

**How to avoid:**
- Use Podman labels to tag all MC-managed containers: `--label mc.case=12345678 --label mc.created=$(date -Iseconds)`
- Reconcile state on startup: `podman ps --filter label=mc.case --format json` to find orphaned containers
- Implement `mc doctor` command to detect and clean mismatches between Podman state and MC metadata
- On container creation, set Podman labels FIRST, then write local metadata
- Store minimal critical metadata in container labels themselves (case number, workspace path)
- Add `--rm` flag for temporary/throwaway containers
- Implement cleanup handlers for signal interrupts (SIGINT, SIGTERM)

**Warning signs:**
- `podman ps -a --filter label=mc.case` shows more containers than `mc list`
- Users report "container already exists" errors
- Disk space grows from accumulating stopped containers
- Container names conflict with new creation attempts

**Phase to address:**
Phase 3 (Container Lifecycle & State Management) - state reconciliation must be designed into the architecture from the beginning as retrofit is complex and error-prone.

---

### Pitfall 5: Platform-Specific Terminal Launcher Failures

**What goes wrong:**
`mc attach` works perfectly on developer's macOS with iTerm2 but fails in production Linux environments, or vice versa. Error messages like "command not found: Terminal.app" or "gnome-terminal is not installed" confuse users. Some terminal emulators don't support the required command-line flags for programmatic launching.

**Why it happens:**
Different platforms have different default terminal emulators with incompatible CLIs:
- macOS: Terminal.app (uses `open -a`), iTerm2 (different launch mechanism)
- Linux: gnome-terminal, konsole, xterm, alacritty (each with different flags)
- Detection logic assumes presence of specific terminals
- Environment variables like `$TERM` show terminal type, not terminal emulator binary

**How to avoid:**
- Implement terminal emulator detection waterfall: check for known emulators in priority order
- macOS: Check for iTerm2 first, fall back to Terminal.app
- Linux: Check `$TERMINAL` env var, then probe for gnome-terminal, konsole, xterm
- Provide configuration option: `mc config set terminal_emulator /usr/bin/kitty`
- Test on minimal systems without GUI (should fail gracefully with helpful message)
- Document supported terminal emulators and fallback behavior
- Consider cross-platform solutions (WezTerm, Alacritty, Kitty work on both macOS and Linux with consistent APIs)

**Warning signs:**
- Works on one developer machine but not others
- CI/CD can't test terminal attachment (headless environments)
- User reports "no terminal opened" with no error message
- Different error messages on macOS vs Linux

**Phase to address:**
Phase 4 (Terminal Attachment & Exec) - terminal launcher must be thoroughly tested across platforms before shipping the attachment feature.

---

### Pitfall 6: Port Binding Conflicts Below 1024

**What goes wrong:**
User wants to run a container that binds to port 443 or 80 for testing SSL/HTTP services, but rootless Podman refuses with "permission denied" errors because ports below 1024 require elevated privileges.

**Why it happens:**
The Linux kernel prevents processes without CAP_NET_BIND_SERVICE capability from binding to ports below 1024 (privileged ports). Rootless Podman runs without privileges by design. Default `net.ipv4.ip_unprivileged_port_start` is 1024.

**How to avoid:**
- Document clearly that privileged ports require either:
  - System-level config change: `sysctl net.ipv4.ip_unprivileged_port_start=443` (requires root)
  - Port mapping to high ports: `-p 8443:443` (map container's 443 to host's 8443)
  - Rootful Podman (defeats security benefits)
- Design container images to use high ports by default (8080 instead of 80)
- For MC use case, containers likely don't need exposed ports (isolated workspaces), so document this limitation without fixing it
- Provide clear error message if port binding fails: "Cannot bind to port 443 (requires privileged access). Use port 8443 or higher."

**Warning signs:**
- Errors mentioning "permission denied" + port numbers
- Works with `-p 8080:8080` but fails with `-p 80:80`
- User requests `sudo podman` to work around

**Phase to address:**
Phase 1 (Container Architecture & Podman Integration) - document port binding limitations during architecture design so users understand constraints upfront.

---

### Pitfall 7: Cgroups v1 Breaks Resource Limits and Logging

**What goes wrong:**
Resource limits (`--memory`, `--cpus`) silently fail or containers can't be stopped cleanly. Container logs are missing or incomplete when using systemd log driver.

**Why it happens:**
Rootless Podman requires cgroups v2 for proper resource delegation. On systems still using cgroups v1 (older Linux distributions, some enterprise systems), hierarchical delegation doesn't work correctly for non-root users. Resource limits are ignored, and systemd logging integration breaks.

**How to avoid:**
- Check cgroups version on startup: `podman info | grep cgroupVersion`
- For MC v2.0, require cgroups v2 in documentation and startup checks
- Provide clear error message if cgroups v1 detected: "MC requires cgroups v2. Your system uses cgroups v1. See [migration guide]."
- Test on RHEL 7/CentOS 7 systems (cgroups v1) to verify graceful degradation
- If supporting cgroups v1 is required, disable resource limits and document limitations

**Warning signs:**
- `podman info` shows `cgroupVersion: v1`
- Resource limits have no effect (container uses more memory than `--memory` limit)
- `podman logs` returns empty or incomplete output
- Containers can't be stopped with `podman stop` (require `podman kill`)

**Phase to address:**
Phase 1 (Container Architecture & Podman Integration) - system requirements must be validated early to prevent shipping incompatible software.

---

### Pitfall 8: Stale Container Metadata After External Podman Operations

**What goes wrong:**
User runs `podman stop <container>` or `podman rm <container>` directly instead of using `mc stop` or `mc rm`. MC's metadata becomes inconsistent - `mc list` shows stopped container as running, or lists deleted containers.

**Why it happens:**
MC maintains its own metadata (state files, database, cache) separate from Podman's container state. External operations (manual `podman` commands, other tools like Portainer) modify Podman state without updating MC metadata. MC doesn't detect the divergence until operations fail.

**How to avoid:**
- Implement state reconciliation on every `mc list` and `mc attach`: query Podman for actual container state via `podman ps --filter label=mc.case`
- Compare Podman state against MC metadata, flag mismatches
- Provide `mc sync` command to reconcile and update metadata based on Podman truth
- Use Podman labels as source of truth for existence checks
- Consider warning users if containers are modified externally
- Auto-cleanup: remove MC metadata for containers that no longer exist in Podman

**Warning signs:**
- `mc list` shows different results than `podman ps --filter label=mc.case`
- Operations fail with "container not found" despite `mc list` showing them
- User reports manual cleanup with `podman rm` doesn't remove from MC
- Stale entries accumulate over time

**Phase to address:**
Phase 3 (Container Lifecycle & State Management) - reconciliation logic should be part of state management architecture from the start.

---

### Pitfall 9: Salesforce Rate Limiting During Bulk Operations

**What goes wrong:**
User creates containers for 30 cases in a script loop, and after 10-15 iterations, Salesforce API starts returning 429 rate limit errors. Container creation partially succeeds (container exists but metadata fetch failed), leaving incomplete state.

**Why it happens:**
Salesforce enforces rate limits: 100,000 daily API calls for Enterprise Edition + 1,000 per user license, with additional limits on concurrent requests (25 long-running requests max). Bulk operations can exhaust per-second or per-minute quotas quickly. MC makes multiple API calls per container (case metadata, account info, possibly attachments).

**How to avoid:**
- Implement request throttling: max 5 API calls per second to Salesforce
- Batch operations: fetch metadata for multiple cases in fewer API calls if Salesforce API supports it
- Cache aggressively: 30-minute TTL on case metadata (already implemented in v1.0), extend to 24 hours for immutable data
- Handle 429 errors gracefully: exponential backoff with jitter (already using `backoff` library)
- Track API usage: log requests, implement local rate limit counter
- Provide bulk operation command: `mc create-batch --cases 12345678,12345679,12345680` with built-in throttling
- Document Salesforce rate limits and recommend batch size limits

**Warning signs:**
- HTTP 429 "Request rate exceeded" errors from Salesforce
- Intermittent failures during bulk operations
- Success rate decreases as number of operations increases
- Errors mention "API request limit exceeded"

**Phase to address:**
Phase 2 (Salesforce Integration & Case Resolution) - rate limiting strategy must be designed before bulk operations are implemented.

---

### Pitfall 10: Container Image Version Drift

**What goes wrong:**
Containers created weeks apart have different tool versions (older container has `oc` 4.12, newer has `oc` 4.15). User switches between containers and experiences inconsistent behavior. Security vulnerabilities accumulate in old containers using outdated base images.

**Why it happens:**
Container images are built at a point in time and don't auto-update. The `mc` CLI might pull `registry.example.com/mc-workspace:latest` which resolves to different image digests over time. Existing containers continue using old images even after new ones are published. No mechanism enforces image updates.

**How to avoid:**
- Pin image to specific digest in production: `registry.example.com/mc-workspace@sha256:abc123...` instead of `:latest`
- Implement `mc upgrade` command to detect outdated containers and offer rebuild
- Tag images with version and creation date: `mc-workspace:v2.0-20260126`
- Check for image updates on `mc create`: compare container's image digest against latest available
- Provide `mc doctor` subcommand: scan for containers using images with known CVEs (integrate with Podman's vulnerability scanning)
- Document image lifecycle: "Images are updated weekly, rebuild containers monthly"
- Consider auto-rebuild policy: warn if container image is >30 days old

**Warning signs:**
- `podman inspect <container> | jq '.[0].ImageDigest'` differs across containers
- Different tool versions across containers created at different times
- Security scanners report CVEs in running containers
- User reports "it works in one container but not another"

**Phase to address:**
Phase 5 (Image Management & Maintenance) - image versioning strategy must be defined when building the initial image to prevent tech debt.

---

### Pitfall 11: TTY Allocation Breaks Programmatic Output

**What goes wrong:**
`mc exec <case> <command>` works for interactive shells but fails when piping output or using in scripts. Output is mangled with control characters, STDOUT and STDERR are mixed, pipes hang unexpectedly.

**Why it happens:**
`podman exec -it` allocates a pseudo-TTY which combines STDOUT/STDERR, inserts control characters, and can hang pipes. This is correct for interactive use but breaks automation. Developers test only interactive scenarios and miss programmatic usage.

**How to avoid:**
- Detect if STDOUT is a TTY: use `-it` for interactive, `-i` only for pipes/scripts
- In Python: `sys.stdout.isatty()` to check if running interactively
- Document the difference: `mc attach` uses `-it`, `mc exec` uses `-i` only
- Test both: `mc exec <case> ls` (interactive) and `mc exec <case> ls | grep foo` (piped)
- Provide `--interactive` flag to force TTY allocation when needed

**Warning signs:**
- `mc exec <case> command > output.txt` produces garbled text
- `mc exec <case> command | jq` fails to parse JSON
- Control characters (^M, ^[[) appear in captured output
- Piped commands hang indefinitely

**Phase to address:**
Phase 4 (Terminal Attachment & Exec) - TTY behavior must be tested for both interactive and programmatic use cases.

---

### Pitfall 12: macOS Podman Machine Not Started

**What goes wrong:**
On macOS, user runs `mc create` and gets cryptic error "Cannot connect to Podman. Is the service running?" because the Podman machine VM isn't started. On Linux this works fine, creating confusing platform-specific behavior.

**Why it happens:**
macOS requires a Podman machine (Linux VM) to run containers. `podman machine start` must be run before container operations. Linux runs Podman natively without a machine. Developers on Linux don't discover this until macOS users report issues.

**How to avoid:**
- Detect platform: check if running on macOS
- Check Podman machine status: `podman machine list --format json`
- Auto-start machine if stopped: prompt "Podman machine is stopped. Start it now? [Y/n]"
- Provide clear error: "Podman machine required on macOS. Run: podman machine init && podman machine start"
- Test on both macOS and Linux throughout development
- Document platform differences in installation guide

**Warning signs:**
- Works on Linux CI but fails for macOS users
- Errors mentioning "connection refused" or "socket not found"
- `podman machine list` shows machine in "stopped" state
- User reports "podman ps works but mc create doesn't"

**Phase to address:**
Phase 1 (Container Architecture & Podman Integration) - platform detection and machine management must be handled from the start.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store metadata only in local files (not Podman labels) | Simpler implementation, no Podman API for labels | State divergence when containers modified externally, no reconciliation possible | Never - labels are critical for state recovery |
| Assume single user on system | Skip user isolation, simpler paths | Multi-user systems create workspace collisions, permission issues | Only for personal dev tools explicitly documented as single-user |
| Use `:latest` tag for container images | Always get newest features | Unpredictable behavior, version drift, broken reproducibility | Development only, never production |
| Skip Salesforce token refresh logic | Fewer edge cases to handle | Failures after 2 hours of use, poor user experience | Never - token expiration is guaranteed |
| Hard-code terminal emulator | Works on developer's machine | Breaks for users with different setups, platform lock-in | Never - cross-platform support is core requirement |
| Ignore cgroups version check | Works on modern systems | Silent failures on RHEL 7, CentOS 7, older Ubuntu | Only if minimum system requirements explicitly exclude cgroups v1 |
| Store all state in memory (no persistence) | Fast, simple | State lost on crash/restart, orphan cleanup impossible | Never - persistence is critical for recovery |
| Use `--rm` on all containers | Auto-cleanup, simple | Can't debug stopped containers, lose forensic data | Only for explicitly temporary operations, never for workspace containers |
| Skip platform detection (macOS vs Linux) | Simpler code, fewer branches | Silent failures on different platforms | Never - cross-platform support is requirement |
| Pass `-it` to all exec commands | Works for interactive use | Breaks pipes, scripts, automation | Never - detect TTY context dynamically |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Salesforce API | Request new access token on every API call | Cache tokens with expiration, refresh 5 minutes before expiry |
| Salesforce API | Treat all errors as fatal | Distinguish transient (429, 503) from permanent (401 with expired refresh token); retry transient, prompt re-auth for permanent |
| Salesforce API | Assume unlimited API calls | Implement request throttling (5/sec), monitor 429 responses, use exponential backoff |
| Salesforce OAuth | Store only access tokens | Store refresh tokens securely to enable automatic re-authentication without user interaction |
| Salesforce OAuth | Ignore `expires_in` response field | Parse and store expiration timestamp to enable proactive refresh |
| Podman API | Parse human-readable output (`podman ps` text) | Use `--format json` to get structured, machine-parseable output |
| Podman API | Assume Podman is installed | Check `podman --version` on startup, provide clear installation instructions if missing |
| Podman API | Use rootful Podman for simplicity | Commit to rootless for security; handle limitations instead of escalating privileges |
| Podman machine (macOS) | Assume machine is always running | Detect machine state, auto-start or prompt user |
| Terminal emulators | Hard-code path to `gnome-terminal` | Detect available emulators dynamically, support multiple options, allow user configuration |
| Terminal emulators | Assume terminal is available | Detect headless environments (CI/CD, SSH without X11), provide graceful degradation or alternative (print command to run manually) |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching case metadata on every `mc list` | Slow listing, API rate limits | Cache metadata with 30-minute TTL (already implemented in v1.0), refresh only when explicitly requested | >20 containers with uncached metadata |
| Creating containers serially in bulk operations | Very slow for multiple cases, user waits minutes | Parallelize with `asyncio` or thread pool, but respect API rate limits | >5 cases created in sequence |
| Storing all container metadata in single JSON file | File corruption risk, lock contention | Use per-container state files or lightweight DB (SQLite) | >100 containers |
| Linear search through containers for case number | Slow lookups as containers grow | Index containers by case number (dict/hashmap), or use Podman label filtering | >50 containers |
| Pulling container image on every `mc create` | Very slow, wastes bandwidth | Check if image exists locally first: `podman image exists`, only pull if missing or explicit `--pull` flag | Every container creation without local cache |
| Starting containers without resource limits | Resource exhaustion if container misbehaves | Set reasonable defaults: `--memory=4g --cpus=2`, allow override | First container that leaks memory/CPU |
| Not reusing Podman machine on macOS | Slow startup (30+ seconds per operation) | Start machine once, keep running, reuse for all operations | Every command on macOS |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Salesforce tokens in container labels | Token exposure in Podman metadata, accessible to all users with Podman access | Store tokens in host filesystem with 0600 permissions, pass to containers via environment variables at runtime only |
| Running containers with `--privileged` flag | Breaks rootless security model, container can escape to host | Never use `--privileged`; document specific capabilities if needed (`--cap-add=CAP_NET_RAW` for ping) |
| Mounting sensitive directories with write access | Container could modify SSH keys, shell config, other credentials | Mount workspace as read-write, mount config dirs as read-only (`:ro` suffix) |
| Trusting Podman labels as authentication | Any user can create containers with `--label mc.case=12345678` | Labels are metadata only, not security boundaries; implement actual authorization checks if multi-user support is added |
| Disabling SSL verification for Salesforce API | Man-in-the-middle attacks, credential theft | Always use `verify=True` for requests (already implemented in v1.0), handle certificate errors explicitly |
| Storing offline refresh token in plaintext config | Token theft allows impersonation | Encrypt refresh tokens or rely on OS-level filesystem permissions (0600) and secure config directory |
| Not validating case numbers before creating containers | Path traversal via case number like `../../etc/passwd` | Validate case number format (8 digits only, already implemented in v1.0), sanitize inputs |
| Passing sensitive data via command-line args | Visible in `ps aux`, logged in shell history | Use environment variables or stdin for credentials, never CLI args |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent failures when terminal launcher fails | User runs `mc attach`, nothing happens, no error message | Always print error explaining why (terminal not found, headless environment), suggest workarounds |
| Creating containers without checking if case exists in Salesforce | Container created but metadata fetch fails, half-initialized state | Validate case existence via API before creating container, fail fast with clear message |
| Not showing container status during creation | User waits with no feedback, assumes command hung | Stream progress: "Pulling image...", "Creating container...", "Fetching case metadata...", "Ready" |
| Cryptic Podman errors passed through to user | User sees `ERRO[0000] cannot mkdir /run/user/1000/libpod: Read-only file system` | Catch common Podman errors, translate to user-friendly messages: "Cannot create container: home directory is read-only" |
| No indication that container is already running | User runs `mc create 12345678` twice, gets error or duplicate | Check for existing container first, offer to attach instead: "Container for case 12345678 already exists. Use 'mc attach 12345678' to connect." |
| Long commands with many flags required for common operations | `mc create --case 12345678 --image mc-workspace:latest --workspace ~/cases/12345678` is tedious | Provide sensible defaults, auto-generate workspace path from case number, make image configurable in config file |
| No way to distinguish containers created by different MC versions | User confused why old containers behave differently | Add version label to containers: `--label mc.version=2.0.0` |
| macOS-specific errors without platform context | "Podman machine not found" confuses Linux users reading docs | Platform-specific error messages: "On macOS, run: podman machine init" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Container creation:** Often missing cleanup on partial failures — verify rollback (remove container if metadata creation fails)
- [ ] **Terminal attachment:** Often missing detection of headless environments — verify graceful failure with helpful message when no display available
- [ ] **Salesforce integration:** Often missing refresh token renewal — verify handling when refresh token itself expires (prompt re-authentication)
- [ ] **Container listing:** Often missing reconciliation with actual Podman state — verify `mc list` matches `podman ps --filter label=mc.case`
- [ ] **State management:** Often missing signal handlers — verify cleanup on Ctrl+C during container creation
- [ ] **Image pulling:** Often missing progress indication — verify user sees progress for long pulls
- [ ] **Error messages:** Often missing actionable suggestions — verify errors explain what to do ("Run: mc login" not just "Authentication failed")
- [ ] **Cross-platform support:** Often missing macOS testing when developed on Linux — verify terminal launcher, paths, Podman machine on macOS
- [ ] **Resource cleanup:** Often missing orphan container detection — verify `mc doctor` finds and reports containers without metadata
- [ ] **API rate limiting:** Often missing backoff for 429 responses — verify exponential backoff with jitter (backoff library already used in v1.0)
- [ ] **Version compatibility:** Often missing migration for containers created by previous MC versions — verify v2.0 can list/attach to v1.0 containers (if applicable)
- [ ] **TTY detection:** Often missing `isatty()` check — verify `mc exec` works both interactively and when piped
- [ ] **Volume permissions:** Often missing UID mapping tests — verify files created in container are accessible on host

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| UID/GID permission issues on mounted volumes | LOW | 1. Stop container 2. Run `podman unshare chown -R $(id -u):$(id -g) ~/cases/12345678` to fix ownership 3. Recreate container with `--userns=keep-id` |
| Pasta networking prevents container communication | LOW | 1. Stop affected containers 2. Recreate with `--network slirp4netns` flag 3. Update MC config to default to slirp4netns |
| Salesforce token expired | LOW | 1. Detect 401 with "invalid_grant" 2. Attempt refresh 3. On refresh failure, prompt user: "Run: mc login" 4. Clear cached tokens |
| Orphaned containers accumulating | LOW | 1. Run `mc doctor --cleanup` 2. Lists orphans via `podman ps -a --filter label=mc.case` 3. User confirms removal 4. Clean metadata |
| Stale metadata after external Podman operations | LOW | 1. Run `mc sync` 2. Query Podman for container state 3. Update MC metadata to match 4. Warn user about external modifications |
| Rate limit exceeded (429) | LOW | 1. Catch 429 response 2. Extract Retry-After header if present 3. Sleep with exponential backoff 4. Retry request 5. Fail after 3 attempts with helpful message |
| Terminal launcher fails | LOW | 1. Detect failure (exit code or exception) 2. Print container connection command: `podman exec -it <container> bash` 3. User runs manually |
| Port binding conflicts (<1024) | MEDIUM | 1. Detect port binding error 2. Suggest alternative: "Change port to 8080 or configure sysctl" 3. Provide documentation link |
| Cgroups v1 detected | MEDIUM | 1. On startup, check `podman info | grep cgroupVersion` 2. If v1, print warning 3. Disable resource limits 4. Document migration to cgroups v2 |
| Container image version drift | MEDIUM | 1. Add `mc upgrade --case 12345678` command 2. Stop old container 3. Pull latest image 4. Create new container with same workspace 5. Preserve metadata |
| Refresh token expired (5 concurrent limit hit) | HIGH | 1. Detect permanent 401 2. Clear all cached tokens 3. Prompt: "Re-authentication required. Run: mc login" 4. After re-auth, recreate refresh token |
| Corrupted container state (metadata/Podman mismatch) | HIGH | 1. Backup metadata 2. Remove corrupted container: `podman rm -f <container>` 3. Remove MC metadata 4. Recreate from scratch using case number |
| macOS Podman machine not started | LOW | 1. Detect platform 2. Check `podman machine list` 3. Prompt: "Start Podman machine? [Y/n]" 4. Run `podman machine start` 5. Retry operation |
| TTY breaks piped output | LOW | 1. Detect if STDOUT is TTY (`sys.stdout.isatty()`) 2. Use `-i` only for pipes 3. Use `-it` for interactive 4. Document behavior |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| UID/GID mapping confusion | Phase 1 (Architecture) | Verify files created in mounted volumes are accessible from host with correct permissions |
| Pasta networking issues | Phase 1 (Architecture) | Verify network smoke tests pass on Podman 5.0+ with pasta enabled |
| Port binding conflicts | Phase 1 (Architecture) | Verify documentation clearly states port binding limitations, test error message |
| Cgroups v1 incompatibility | Phase 1 (Architecture) | Verify startup check detects cgroups version and warns/fails appropriately |
| macOS Podman machine detection | Phase 1 (Architecture) | Verify macOS users prompted to start machine, auto-start works |
| Salesforce token expiration | Phase 2 (Salesforce Integration) | Verify tokens auto-refresh 5 minutes before expiry, manual refresh succeeds |
| Salesforce rate limiting | Phase 2 (Salesforce Integration) | Verify 429 responses trigger exponential backoff, test bulk operations |
| Orphaned containers | Phase 3 (Lifecycle Management) | Verify `mc doctor` detects orphans after simulated crashes (kill -9) |
| Stale metadata | Phase 3 (Lifecycle Management) | Verify `mc list` reconciles with Podman state, `mc sync` command works |
| Terminal launcher failures | Phase 4 (Terminal Attachment) | Verify graceful failure on headless systems, test on macOS Terminal, iTerm2, Linux gnome-terminal, konsole |
| TTY allocation breaks pipes | Phase 4 (Terminal Attachment) | Verify `mc exec` works both interactively and when piped: `mc exec <case> ls \| grep foo` |
| Image version drift | Phase 5 (Image Management) | Verify `mc upgrade` detects outdated images, rebuild preserves workspace data |

---

## Sources

### Rootless Podman
- [Podman Rootless Tutorial](https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md) - Official rootless guide
- [Podman Rootless Documentation](https://github.com/containers/podman/blob/main/rootless.md) - Comprehensive limitations reference (HIGH confidence)
- [SUSE Rootless Podman Guide](https://documentation.suse.com/smart/container/html/rootless-podman/index.html) - Platform-specific gotchas
- [Red Hat: Running Rootless Podman](https://www.redhat.com/en/blog/rootless-podman-makes-sense) - Security benefits and tradeoffs
- [Rootless Docker Caveats](https://joeeey.com/blog/rootless-docker-avoiding-common-caveats/) - Common mistakes (applies to Podman)
- [Deep Dive: Podman in 2026](https://dev.to/dataformathub/deep-dive-why-podman-and-containerd-20-are-replacing-docker-in-2026-32ak) - Recent adoption trends

### User Namespaces & Permissions
- [Podman and User Namespaces](https://opensource.com/article/18/12/podman-and-user-namespaces) - UID/GID mapping explained
- [Using Volumes with Rootless Podman](https://www.tutorialworks.com/podman-rootless-volumes/) - Volume permission strategies (HIGH confidence)
- [Container Permission Denied Errors](https://www.redhat.com/en/blog/container-permission-denied-errors) - Debugging guide
- [Rootless Podman User Namespace Modes](https://www.redhat.com/en/blog/rootless-podman-user-namespace-modes) - Advanced configuration

### Podman Platform Differences
- [Podman vs Docker 2026](https://last9.io/blog/podman-vs-docker/) - Current state comparison
- [Podman Installation](https://podman.io/docs/installation) - Official installation guide showing platform differences (MEDIUM confidence)
- [Podman Machine Documentation](https://docs.podman.io/en/v5.2.2/markdown/podman-machine.1.html) - macOS/Windows VM layer explained (HIGH confidence)

### Container Lifecycle & State Management
- [Container Lifecycle Operations](https://deepwiki.com/containers/podman/3.2-container-lifecycle-management) - State transitions
- [Container Lifecycle Best Practices](https://daily.dev/blog/docker-container-lifecycle-management-best-practices) - Cleanup patterns
- [Understanding Container Lifecycle](https://cycle.io/learn/container-lifecycle) - State management fundamentals

### Podman Exec & Terminal Attachment
- [Podman Exec Documentation](https://docs.podman.io/en/latest/markdown/podman-exec.1.html) - Official exec reference (HIGH confidence)
- [Podman Attach Methods](https://devtodevops.com/blog/podman-attach-to-running-container-bash/) - Interactive attachment guide
- [Docker Attach vs Exec](https://iximiuz.com/en/posts/containers-101-attach-vs-exec/) - Conceptual differences

### Terminal Emulators
- [Awesome Terminals](https://github.com/cdleon/awesome-terminals) - Comprehensive terminal emulator list
- [WezTerm](https://wezterm.org/index.html) - Cross-platform terminal with programmatic API
- [Alacritty](https://alacritty.org/) - Cross-platform GPU-accelerated terminal
- [Ghostty](https://github.com/ghostty-org/ghostty) - Modern cross-platform terminal (2026)
- [Terminal Launch Library](https://github.com/skywind3000/terminal) - Python cross-platform terminal launcher (MEDIUM confidence)

### Salesforce API
- [Salesforce Rate Limiting Best Practices](https://developer.salesforce.com/docs/marketing/marketing-cloud/guide/rate-limiting-best-practices.html) - Official guidelines (HIGH confidence)
- [Salesforce API Limits](https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/salesforce_app_limits_platform_api.htm) - Official limits reference (HIGH confidence)
- [API Limits Monitoring 2024](https://developer.salesforce.com/blogs/2024/11/api-limits-and-monitoring-your-api-usage) - Recent best practices
- [OAuth Refresh Token Flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_refresh_token_flow.htm&language=en_US&type=5) - Official OAuth docs (HIGH confidence)
- [Salesforce OAuth invalid_grant](https://nango.dev/blog/salesforce-oauth-refresh-token-invalid-grant) - Common error handling

### Container Image Security
- [Container Image Security 2026](https://www.cleanstart.com/guide/container-image-security) - Modern security practices
- [Red Hat Container Updates](https://access.redhat.com/articles/2208321) - Update SLAs and policies
- [Docker Hardened Images](https://www.docker.com/blog/docker-hardened-images-for-every-developer/) - CVE remediation in 7 days

### Migration & Compatibility
- [Database Backward Compatibility Patterns](https://www.pingcap.com/article/database-design-patterns-for-ensuring-backward-compatibility/) - Expand-migrate-contract pattern
- [Docker Alternatives 2026](https://signoz.io/comparisons/docker-alternatives/) - Migration strategies
- [Containers 2025: Docker vs Podman](https://www.linuxjournal.com/content/containers-2025-docker-vs-podman-modern-developers) - Recent comparison

---

*Pitfalls research for: MC v2.0 Container Orchestration*
*Researched: 2026-01-26*
*Confidence: HIGH for Podman and Salesforce API, MEDIUM for terminal emulator specifics*
