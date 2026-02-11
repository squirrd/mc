# Pitfalls Research: Auto-Update for CLI Tools

**Domain:** Auto-update functionality for existing CLI tools
**Researched:** 2026-02-11
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Synchronous Version Check Blocking Startup

**What goes wrong:**
CLI performs version check on every invocation, blocking the command from running until the API responds. Users experience 3-13 second delays before `mc --help` even displays, making the tool feel broken.

**Why it happens:**
Developers implement version checking in startup initialization because it's the "obvious" place - before the command runs. This creates synchronous blocking network requests before argument parsing, making every command (even offline operations like `--help`) wait for external APIs.

**How to avoid:**
- Implement async background version checking with timestamp-based throttling (hourly minimum)
- Store last check timestamp in config file, skip check if within throttle window
- Never block command execution waiting for version check
- Use stale-while-revalidate pattern: show cached version status immediately, update in background
- Perform check AFTER command execution completes, not before

**Warning signs:**
- `time mc --help` takes >500ms
- Network timeouts cause CLI to hang
- Users report CLI feels slow or unresponsive
- Offline usage breaks the tool

**Phase to address:**
Phase 1: Version Check Infrastructure - Must establish non-blocking architecture from the start. Retrofitting is significantly harder.

**Recovery cost:** HIGH - Requires refactoring entire startup sequence if implemented wrong initially.

---

### Pitfall 2: GitHub API Rate Limiting Without Fallback

**What goes wrong:**
Unauthenticated GitHub releases API has 60 requests/hour limit. Multiple users behind same corporate NAT IP, CI/CD systems, or aggressive version checking exhaust rate limit. CLI crashes with HTTP 429 errors or shows confusing "update check failed" messages.

**Why it happens:**
Developers test with authenticated tokens (5,000 req/hour) or single-user scenarios, never hitting the 60 req/hour unauthenticated limit. Production deployments with many users behind shared IPs immediately hit rate limits.

**How to avoid:**
- Implement exponential backoff with jitter for rate limit responses (HTTP 429)
- Use ETag conditional requests (`If-None-Match` header) to avoid consuming rate limit quota when version hasn't changed - conditional requests don't count against rate limit for 304 Not Modified responses
- Store ETag from previous response, include in next request
- Cache `x-ratelimit-remaining` and `x-ratelimit-reset` headers
- When rate limited, gracefully degrade: use cached version info, suppress update checks until reset time
- Never crash or block commands due to rate limit - fail open, not closed
- Consider GitHub token support for power users (5,000 req/hour) but don't require it

**Warning signs:**
- Frequent "HTTP 429" errors in logs
- Version checks failing during business hours
- Users in same organization reporting simultaneous failures
- Rate limit headers showing `x-ratelimit-remaining: 0`

**Phase to address:**
Phase 1: Version Check Infrastructure - ETag support and rate limit handling must be part of initial implementation.

**Recovery cost:** MEDIUM - Can add ETag support and rate limit handling retroactively, but requires API client refactoring.

---

### Pitfall 3: uv tool upgrade Failure Leaving Broken Installation

**What goes wrong:**
`uv tool upgrade mc` fails partway through (network error, disk full, Python version mismatch). Tool installation is now broken - old version deleted but new version incomplete. Running `mc` produces "command not found" or import errors. Auto-update feature just bricked the user's installation.

**Why it happens:**
`uv tool upgrade` doesn't have atomic transactions. If upgrade fails, the tool environment may be broken, and symlinks to Python may be invalid. On Windows, upgrading while tool is in use fails with file access errors. When Python version used by tool is upgraded/removed, all tools become unusable without manual `uv tool install --force`.

**How to avoid:**
- Never auto-upgrade without user confirmation for major versions
- Implement health check before upgrade: `uv tool list --outdated` to verify new version exists
- After upgrade attempt, validate installation: run `mc --version` to confirm
- On upgrade failure, provide recovery instructions: `uv tool install --force mc`
- Don't upgrade while tool is running - warn "Close all mc sessions before upgrading"
- For Python version mismatches, document recovery: reinstall old Python, upgrade to new version with `--python 3.13`, uninstall old Python
- Consider manual-only upgrades (no silent auto-upgrade) - just notify users with banner and instructions

**Warning signs:**
- Upgrade exit code non-zero but no error handling
- `mc --version` fails after upgrade attempt
- Import errors after version update
- Windows file access errors during upgrade

**Phase to address:**
Phase 2: Auto-Update Mechanics - Must include upgrade validation and rollback instructions before shipping auto-update.

**Recovery cost:** HIGH - Broken installation requires manual intervention. Users may lose trust in tool.

---

### Pitfall 4: Concurrent Config File Writes Causing Corruption

**What goes wrong:**
Multiple `mc` processes run simultaneously (user opens several cases). Each updates last version check timestamp, pin status, or notification suppression in `config.toml`. Concurrent writes corrupt the file - TOML parser fails, all config lost, tool unusable.

**Why it happens:**
TOML libraries (tomli/tomllib) don't provide file locking or atomic writes. Standard pattern is: read entire file → modify in-memory → write entire file. Two processes doing this simultaneously cause race condition: Process A reads, Process B reads, Process A writes, Process B writes (overwriting A's changes or corrupting file).

**How to avoid:**
- Use atomic write pattern: write to temp file, fsync, rename (atomic on POSIX)
- Implement file locking before config updates (use `filelock` library from PyPI)
- Use tomlkit (not tomli) for AST-based editing that preserves formatting and reduces corruption risk
- Keep version check state in separate file from main config (reduces lock contention)
- Use SQLite for state that changes frequently (automatic locking and transactions)
- Read-modify-write with file lock:
  ```python
  from filelock import FileLock
  lock = FileLock("config.toml.lock")
  with lock:
      config = read_toml()
      config['last_check'] = now()
      atomic_write_toml(config)
  ```
- Handle corrupted config gracefully: backup, recreate with defaults, warn user

**Warning signs:**
- TOML parsing errors in production
- "File contains parsing errors" exceptions
- Config changes randomly disappearing
- Users running multiple mc instances simultaneously

**Phase to address:**
Phase 1: Version Check Infrastructure - File locking must be implemented when version check writes first timestamp.

**Recovery cost:** MEDIUM - Can add file locking retroactively but requires refactoring all config write paths.

---

### Pitfall 5: Infinite Update Loop from Version Comparison Bug

**What goes wrong:**
Version comparison logic has bug (e.g., "2.0.10" < "2.0.9" string comparison instead of semantic versioning). CLI thinks current version is always outdated. User accepts update, upgrade completes, CLI immediately prompts to update again. Infinite loop consumes bandwidth, frustrates users, causes support tickets.

**Why it happens:**
String comparison instead of semantic version parsing: "2.0.10" < "2.0.9" because "1" < "9". Pre-release version handling wrong (is "2.1.0-beta" newer than "2.0.9"?). Version normalization missing ("v2.0.1" vs "2.0.1" treated as different versions).

**How to avoid:**
- Use semantic version library (packaging.version.Version) for all comparisons
- Normalize versions before comparison (strip "v" prefix)
- Handle pre-release versions correctly (2.1.0-beta should be < 2.1.0)
- Store "last offered version" separately from "current version" to detect loop
- Add safeguard: if offered same version 3+ times, suppress notifications for 7 days
- Test version comparison with edge cases:
  - Pre-release: 2.0.0-alpha, 2.0.0-beta, 2.0.0-rc1, 2.0.0
  - Multi-digit: 1.9.0 vs 1.10.0 vs 1.11.0
  - Prefix variations: v2.0.1 vs 2.0.1
- Never auto-update to pre-release unless explicitly opted in

**Warning signs:**
- Same version appears in update check repeatedly
- Users report "constant update prompts"
- Pre-release versions offered to stable users
- Version comparison unit tests missing

**Phase to address:**
Phase 1: Version Check Infrastructure - Version comparison is foundational. Must be correct from day one.

**Recovery cost:** LOW - Version comparison is isolated function, easy to fix. But trust damage is done.

---

### Pitfall 6: Update Notification Spam Training Users to Ignore

**What goes wrong:**
CLI shows update banner on every command invocation. Users see "Update available: 2.0.5 → 2.0.6" hundreds of times per day. Notification fatigue sets in. Users learn to ignore all CLI messages, missing actual important errors. When critical security update ships, users ignore it.

**Why it happens:**
Developers show notification whenever `latest_version > current_version`. No suppression logic. No consideration for notification frequency vs update significance. "More visibility = better adoption" assumption backfires.

**How to avoid:**
- Show notification maximum once per day per version
- Store `last_notified_version` and `last_notified_timestamp` in config
- Suppress notification if same version already shown in last 24 hours
- Different urgency levels:
  - Patch (2.0.4 → 2.0.5): weekly reminder maximum
  - Minor (2.0.x → 2.1.0): daily reminder acceptable
  - Major (2.x → 3.0): immediate notification, weekly reminder
  - Security: immediate + daily until upgraded
- Provide user control: `mc config set update-notification-frequency <daily|weekly|never>`
- Make notifications dismissible: `mc update dismiss --for 7d`
- Show notification at END of command (after output), not beginning (doesn't interfere)
- Rich banner format with single-line summary, not multi-line disruption:
  ```
  ╭─ Update Available ─────────────────────────────╮
  │ mc 2.0.6 available (you have 2.0.4)            │
  │ Run: mc-update upgrade  │  Dismiss: mc update dismiss --for 7d │
  ╰────────────────────────────────────────────────╯
  ```

**Warning signs:**
- Same banner appears on every command
- No user control over notification frequency
- Users complaining about "nagware"
- Adoption metrics show notification fatigue (low upgrade rate despite high visibility)

**Phase to address:**
Phase 3: Notification UI - After core version checking works, add sophisticated notification suppression.

**Recovery cost:** LOW - Notification logic is UI layer, easy to modify without breaking core functionality.

---

### Pitfall 7: Version Pinning Without Escape Hatch

**What goes wrong:**
User pins to version 2.0.4 to avoid breaking change in 2.1.0. Months pass. Version 2.0.4 has critical security vulnerability patched in 2.0.9 and 2.1.3. User is pinned, never sees security updates, remains vulnerable. No escape hatch to say "pin to 2.0.x but take security patches".

**Why it happens:**
Pin implementation is all-or-nothing: pinned = no updates ever. No semantic versioning awareness (pin to minor version allowing patches). No security override mechanism. Developers assume users will manually review and update pins (they won't).

**How to avoid:**
- Support pin granularity:
  - `mc config pin 2.0.4` - exact version only
  - `mc config pin 2.0.x` - any patch in 2.0 series
  - `mc config pin 2.x` - any minor/patch in 2.0 series
- Implement stale pin warnings after 90 days:
  - "Pinned to 2.0.4 for 94 days. Latest: 2.0.9 (security fixes). Recommend: mc config pin 2.0.x"
- Security override: if CVE metadata available, show critical security notices even when pinned
- Grace period on new pins (7 days no warnings), then weekly reminders
- Make unpin easy: `mc config unpin` with confirmation
- Show what user is missing: `mc version --check` displays changelog summary for skipped versions
- Provide comparison: `mc version compare 2.0.4 2.0.9` shows critical fixes

**Warning signs:**
- No logic differentiating patch/minor/major pins
- Pinned users never receive any notifications
- No mechanism to detect stale pins
- Support tickets about missing security fixes from pinned users

**Phase to address:**
Phase 2: Pin Management - Pin granularity and stale detection must be designed into pin feature.

**Recovery cost:** MEDIUM - Requires refactoring pin storage schema and comparison logic.

---

### Pitfall 8: Stale Version Cache Preventing Update Detection

**What goes wrong:**
Cache stores "latest version: 2.0.5" with 24-hour TTL. New version 2.0.6 released. User runs `mc` multiple times, always sees "up to date" because cache hasn't expired. User manually checks GitHub, sees 2.0.6 released hours ago, files bug report "update check broken".

**Why it happens:**
Cache invalidation is hard. TTL-only approach doesn't detect out-of-band changes (new releases). No cache bypass mechanism. No ETag-based conditional requests to efficiently check for changes without consuming API quota.

**How to avoid:**
- Implement stale-while-revalidate pattern:
  - Return cached version immediately (non-blocking)
  - Trigger background revalidation if cache older than threshold (1 hour)
  - Update cache asynchronously
- Use ETag-based conditional requests (GitHub returns 304 Not Modified if version unchanged)
- Store ETag from previous API response
- Include `If-None-Match: <etag>` header in subsequent requests
- If 304 response, extend cache TTL without consuming API quota
- Provide cache bypass: `mc version --check --force` ignores cache, forces fresh API call
- Multi-tier cache invalidation:
  - Fast path: 1-hour cache for frequent checks
  - Manual check: bypasses cache entirely
  - Background: async revalidation every 6 hours
- Cache corruption recovery: if cache parse fails, delete and rebuild

**Warning signs:**
- Users manually finding new versions before CLI detects them
- No ETag headers being used
- No force-refresh mechanism
- Cache TTL is only invalidation strategy

**Phase to address:**
Phase 1: Version Check Infrastructure - ETag support and cache invalidation strategy are foundational.

**Recovery cost:** MEDIUM - Can add ETag support retroactively but requires API client changes.

---

### Pitfall 9: Quay.io API Failures Blocking Container Operations

**What goes wrong:**
Container version check queries Quay.io API for latest image digest. API is down or rate limited (HTTP 429). Container operations fail: can't start containers, can't pull images. User's workflow blocked by non-essential version check.

**Why it happens:**
Version check is synchronous dependency for container start. No fallback to last-known-good version. No local caching of registry metadata. Developers assume registry is always available (it isn't).

**How to avoid:**
- Decouple version check from container operations
- Container start should work even if version check fails
- Use local cache of image digests with stale-while-revalidate:
  - Try API check (with timeout: 5s max)
  - If fails, use cached digest
  - Warn user: "Using cached version (registry unreachable)"
- Implement retry with exponential backoff for transient failures
- Quay.io rate limiting is "few requests per second per IP" with bursting:
  - If HTTP 429, back off exponentially (1s, 2s, 4s, 8s max)
  - Don't retry more than 3 times
- Provide manual override: `mc container start --no-version-check` bypasses registry query
- Distinguish warning (version check failed) from error (container operation failed)

**Warning signs:**
- Container operations fail when registry is slow/down
- No timeout on registry API calls
- No cached fallback for registry metadata
- Version check couples to critical path

**Phase to address:**
Phase 2: Container Version Check - Must implement timeout and fallback when adding container version checking.

**Recovery cost:** MEDIUM - Requires decoupling version check from container lifecycle operations.

---

### Pitfall 10: Running Container Not Updated But User Expects It

**What goes wrong:**
User is running container from image 1.0.5. New image 1.0.6 released and auto-pulled. User still working in 1.0.5 container, doesn't realize they need to restart. Reports "bug is still present" even though bug was fixed in 1.0.6.

**Why it happens:**
Container runtime semantics: running container uses the image it was created from, not current image with same tag. Image pull updates local image store but doesn't affect running containers. Users unfamiliar with container lifecycle expect "update applied" means "my environment updated".

**How to avoid:**
- Clear messaging: "New image 1.0.6 available. Running containers unaffected until restart."
- When auto-pull completes, show container-specific guidance:
  ```
  Image mc:1.0.6 downloaded successfully.

  Your running containers are still using 1.0.5:
  - case-12345678 (running, 1.0.5)

  To upgrade: mc container restart 12345678
  Or start new container: mc case 87654321
  ```
- Add `mc container list` flag showing image version mismatch:
  ```
  CASE        STATUS    IMAGE     AVAILABLE
  12345678    running   1.0.5     1.0.6 ⚠
  ```
- Optional auto-restart behavior: `mc config set container-auto-restart on-update`
  - Only safe for stateless containers
  - Requires graceful shutdown (save work first)
- Don't auto-restart without confirmation - data loss risk

**Warning signs:**
- No indication which containers are using old images
- Users confused about when updates take effect
- No guidance on restarting containers
- Auto-restart without user control

**Phase to address:**
Phase 3: Container Update UX - After version checking works, add container lifecycle awareness.

**Recovery cost:** LOW - Purely UI/messaging improvements, no core functionality changes.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip version caching, always query API | Simpler code, always current | Rate limiting, slow startup, offline failure | Never (testing only) |
| String comparison for versions | No library dependency | Infinite loops on 1.10 > 1.9 | Never |
| Synchronous version check in startup | Easy to implement | Blocks all commands, slow tool | Never |
| No file locking on config writes | Simpler implementation | Config corruption with concurrent use | Only if single-instance guaranteed (never for CLI) |
| Silent auto-upgrade without validation | Users always current | Broken installations, lost trust | Never |
| TTL-only cache invalidation | Simple to implement | Stale data for cache duration | Acceptable with short TTL + force refresh option |
| All-or-nothing version pinning | Simple boolean logic | Users stuck on vulnerable versions | Never - need pin granularity |
| Show notification on every command | Maximum visibility | Notification fatigue, ignored warnings | Never |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GitHub Releases API | Unauthenticated requests without rate limit handling | Use ETags for conditional requests, cache x-ratelimit headers, fail gracefully on 429 |
| GitHub Releases API | Fetching full release list every time | Use If-None-Match header with cached ETag, get 304 Not Modified when unchanged |
| Quay.io Registry | No timeout on registry queries | 5-second timeout, exponential backoff on failures, cached fallback |
| Quay.io Registry | Assuming registry is always available | Decouple version check from critical path, fail open (allow operation with warning) |
| uv tool upgrade | No validation after upgrade | Run `mc --version` after upgrade, check exit code, provide recovery instructions on failure |
| uv tool upgrade | Upgrading while tool is running | Detect active sessions (lockfile/pidfile), warn before upgrade, Windows file locking |
| Config file writes | No atomic writes or locking | Use filelock library + atomic write pattern (temp file + rename) |
| Version comparison | String comparison instead of semver | Use packaging.version.Version for all comparisons, normalize versions first |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Version check on every command | Slow startup, network timeouts | Timestamp-based throttling (hourly), async background check | Immediately on slow networks |
| No ETag caching for GitHub API | Rate limiting, quota exhaustion | Store ETag, use If-None-Match header | 60 requests (unauthenticated) |
| Synchronous network calls in startup | Commands block on network | Non-blocking async checks after command | First slow network connection |
| No cache for registry queries | Slow container starts, rate limiting | Cache image digests with TTL, stale-while-revalidate | Heavy container usage |
| Full config rewrite on every change | Config corruption under concurrent load | SQLite for frequent state changes, atomic writes with locking | Multiple simultaneous processes |
| No notification suppression | User trains to ignore messages | Once per day per version maximum, dismissible notifications | Daily active users |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting any SSL certificate for API calls | Man-in-the-middle attacks | Always verify=True, pin certificate for Quay.io if possible |
| Auto-upgrade without signature verification | Malicious update distribution | Verify GitHub release signatures, checksum validation |
| Storing GitHub token in config without encryption | Token exposure via file access | Use keyring library or document token permissions (read-only releases) |
| No version pinning for dependencies in container | Supply chain attack via transitive deps | Pin all container dependencies with SHA256 checksums |
| Executing uv tool upgrade without user confirmation for major versions | Unwanted breaking changes | Require explicit confirmation for major version upgrades |
| No secure temp file handling during upgrade | Race condition allows malicious code injection | Use tempfile.NamedTemporaryFile with delete=False, secure permissions |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing notification at start of command | Disrupts command output, breaks parsing | Show at end of command, after output |
| No way to dismiss notifications | Constant nagging, trains users to ignore | `mc update dismiss --for 7d` command |
| Cryptic "update failed" errors | Users don't know how to recover | Specific error + recovery steps: "uv tool install --force mc" |
| Auto-update without confirmation | Unexpected breaking changes | Always confirm major versions, opt-in for auto-update |
| No indication of what changed | Users don't know if upgrade is worth it | Show changelog summary: "2.0.6: Security fix for CVE-2026-1234" |
| Version pin with no warnings | Users stuck on vulnerable versions | Stale pin warnings after 90 days, show what's missed |
| Update blocks current work | Interrupts user flow | Background download, apply on next invocation |
| No way to check for updates manually | Users can't force refresh | `mc version --check --force` bypasses cache |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Version check:** Often missing ETag support — verify conditional requests work, rate limit not exhausted
- [ ] **Version comparison:** Often missing pre-release handling — verify 2.1.0-beta vs 2.0.9 comparison
- [ ] **Auto-upgrade:** Often missing validation — verify `mc --version` works after upgrade, recovery instructions provided
- [ ] **Config writes:** Often missing file locking — verify concurrent writes don't corrupt config
- [ ] **Notification UI:** Often missing suppression logic — verify same notification not shown repeatedly
- [ ] **Version pinning:** Often missing stale detection — verify warnings after 90 days pinned
- [ ] **Cache invalidation:** Often missing force refresh — verify `--force` flag bypasses cache
- [ ] **Error handling:** Often missing specific recovery steps — verify users know how to fix broken upgrades
- [ ] **Container updates:** Often missing lifecycle messaging — verify users understand restart required
- [ ] **Rate limiting:** Often missing graceful degradation — verify tool works when API rate limited

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Blocked startup from version check | LOW | Kill async task if taking >5s, continue with cached data |
| GitHub rate limited (HTTP 429) | LOW | Use cached version info, suppress checks until x-ratelimit-reset time |
| uv tool upgrade failed, broken install | HIGH | User runs: `uv tool install --force git+https://github.com/org/mc.git` |
| Config file corrupted from concurrent writes | MEDIUM | Detect parse error, backup corrupted file to config.toml.bak, recreate with defaults, warn user |
| Infinite update loop from version bug | MEDIUM | Detect same version offered 3+ times, suppress for 7 days, log bug report instructions |
| Notification spam annoying users | LOW | Immediate hotfix: bump notification suppression to 7 days default |
| Pinned to vulnerable version | MEDIUM | Proactive: email users pinned >90 days. Reactive: security override shows critical CVEs even when pinned |
| Stale cache showing wrong version | LOW | User runs: `mc version --check --force` to bypass cache |
| Quay.io API down, can't check image version | LOW | Graceful degradation: use cached digest, warn "using cached version", container starts normally |
| Running container not updated after image pull | LOW | Clear messaging: `mc container list` shows version mismatch, instructions to restart |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Blocked startup | Phase 1: Version Check Infrastructure | `time mc --help` completes in <500ms even with slow network |
| GitHub rate limiting | Phase 1: Version Check Infrastructure | Tool works gracefully when rate limited, uses ETag conditional requests |
| uv tool upgrade failure | Phase 2: Auto-Update Mechanics | Upgrade validation catches failures, provides recovery instructions |
| Config corruption | Phase 1: Version Check Infrastructure | Concurrent processes don't corrupt config, file locking works |
| Infinite update loop | Phase 1: Version Check Infrastructure | Version comparison unit tests pass for all edge cases |
| Notification spam | Phase 3: Notification UI | Same notification not shown more than once per 24 hours |
| Version pinning without escape | Phase 2: Pin Management | Stale pin warnings work, granular pinning (2.0.x) supported |
| Stale cache | Phase 1: Version Check Infrastructure | `--force` flag bypasses cache, ETag revalidation works |
| Quay.io failures | Phase 2: Container Version Check | Container operations work when registry down, cached fallback works |
| Container update confusion | Phase 3: Container Update UX | Users understand when restart needed, version mismatch visible |

## Sources

**GitHub API Rate Limiting:**
- [GitHub Docs: Rate Limits for REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [A Developer's Guide: Managing Rate Limits for the GitHub API](https://www.lunar.dev/post/a-developers-guide-managing-rate-limits-for-the-github-api)
- [GitHub CLI Discussions: Ways to handle rate limiting](https://github.com/cli/cli/discussions/7754)
- [mise Issue #2263: GitHub API rate limiting](https://github.com/jdx/mise/issues/2263)

**CLI Performance and Startup Issues:**
- [Gemini CLI Issue #4544: Slow startup time (8-12 seconds)](https://github.com/google-gemini/gemini-cli/issues/4544)
- [Why is Gemini CLI So Slow? Investigation into 35 Second Startup Times](https://urjit.io/blog/2025-11-28-the-high-cost-of-a-slow-cli/)

**uv Tool Upgrade Issues:**
- [uv Issue #8028: List and repair broken venvs after Python upgrade](https://github.com/astral-sh/uv/issues/8028)
- [uv Issue #11534: Make upgrade --all tolerant to deleted Python versions](https://github.com/astral-sh/uv/issues/11534)
- [uv Issue #11930: Upgrading tool while in use fails](https://github.com/astral-sh/uv/issues/11930)
- [uv Issue #8528: Windows upgrade doesn't replace executables](https://github.com/astral-sh/uv/issues/8528)
- [uv Docs: Using Tools](https://docs.astral.sh/uv/guides/tools/)

**Quay.io Rate Limiting:**
- [Red Hat Customer Portal: Quay.io rate limiting](https://access.redhat.com/solutions/6218921)
- [Quay.io Documentation: HTTP 429 Errors](https://docs.quay.io/issues/429.html)

**Update Failures and Recovery:**
- [LaunchDarkly: Strategies for Recovering from Failed Deployments](https://launchdarkly.com/blog/strategies-for-recovering-from-failed-deployments/)
- [Windows IT Pro Blog: Scalable Windows Resiliency with Recovery Tools](https://techcommunity.microsoft.com/blog/windows-itpro-blog/scalable-windows-resiliency-with-new-recovery-tools/4470659)
- [Stackademic: Fixing Claude Code's Auto-Update Nightmare](https://blog.stackademic.com/when-your-ai-partner-breaks-fixing-claude-codes-auto-update-nightmare-889f1dd82a63)

**Concurrent File Access:**
- [PyPI: filelock](https://pypi.org/project/filelock/)
- [PyPI: atomicwrites](https://python-atomicwrites.readthedocs.io/)
- [Programming Languages: Python Tomlkit for Robust TOML Parsing](https://johal.in/programming-languages-python-tomlkit-for-robust-toml-file-parsing-and-editing/)

**Cache Invalidation:**
- [How to Build Cache Invalidation Strategies](https://oneuptime.com/blog/post/2026-01-30-cache-invalidation-strategies/view)
- [Caching in 2026: Fundamentals and Invalidation](https://lukasniessen.medium.com/caching-in-2026-fundamentals-invalidation-and-why-it-matters-more-than-ever-867fee46e98b)
- [GitHub Docs: Best Practices for REST API - ETag Conditional Requests](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)

**Notification Best Practices:**
- [App Push Notification Best Practices for 2026](https://appbot.co/blog/app-push-notifications-2026-best-practices/)
- [14 Push Notification Best Practices for 2026](https://reteno.com/blog/push-notification-best-practices-ultimate-guide-for-2026)

**Version Pinning:**
- [arXiv: Pinning Is Futile (2026)](https://arxiv.org/pdf/2502.06662)
- [Alpine Package Keeper: Version Pinning](https://wiki.alpinelinux.org/wiki/Alpine_Package_Keeper)

---
*Pitfalls research for: MC CLI v2.0.4 Auto-Update Milestone*
*Researched: 2026-02-11*
