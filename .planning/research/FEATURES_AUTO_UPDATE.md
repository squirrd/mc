# Feature Research: Auto-Update Systems for CLI Tools

**Domain:** CLI Auto-Update and Version Management
**Researched:** 2026-02-11
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Version check mechanism | CLI tools universally provide `--version` flags; users expect to know what they're running | LOW | Already exists via `--version`. Need to extend to check remote versions |
| Update availability notification | GitHub CLI, rustup, npm all notify when updates exist; silence means "checked and current" | MEDIUM | Must be non-blocking, shown on stderr. GitHub CLI pattern: check every 24h |
| Manual update trigger | Every major CLI has explicit update command (rustup update, brew upgrade, gh upgrade) | LOW | `uv tool upgrade mc-cli` already works. Need to document/promote |
| Graceful network failure | CLI must continue working when offline or registry/API unavailable | MEDIUM | Fallback to cached data, show warning, continue execution. Critical for field work |
| Timestamp-based throttling | Prevents API hammering, respects rate limits, improves UX by not re-checking constantly | MEDIUM | GitHub CLI: 24h window. Recommend hourly for background, daily for user-visible notifications |
| Version source authority | Users need to trust version info comes from official source (GitHub releases, registry) | LOW | Use GitHub Releases API for CLI, Quay.io API for container images |
| Current version indicator | When listing versions, show which is installed/running | LOW | Simple comparison, mark with `(current)` or highlight in output |
| Non-blocking updates | Update checks must not delay command execution or make CLI feel slow | MEDIUM | Background check with cached results. Display on next invocation if available |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Version pinning with grace period | Most tools offer pinning OR warnings, not both. MC offers pin + suppress warnings for X days, then weekly reminders | MEDIUM | Prevents pin-and-forget while respecting intentional version locks. Store pin timestamp in TOML |
| Dual-artifact version management | Manage both CLI tool AND container image versions from single utility | HIGH | Unique to containerized CLI tools. Coordinate updates across two version streams |
| Smart update notifications with context | Not just "update available" but "update available, you're pinned to v1.2.3 (30 days old), run mc-update to unpin" | MEDIUM | Rich contextual banners with actionable hints. Goes beyond basic "new version" messages |
| Container auto-pull with pin respect | Automatically pull new container images unless pinned, with clear warning when running stale pinned version | HIGH | Podman auto-update exists but doesn't integrate with CLI version management. MC ties them together |
| Unified update utility | Single `mc-update` command manages CLI upgrades, container pulls, version listing, and pinning | MEDIUM | Better UX than "use uv tool upgrade for CLI, podman pull for containers" split |
| Version listing with metadata | Show version, release date, and whether it's newer/older than current | LOW | Helps users make informed decisions. Most tools just show numbers without context |
| Stale pin warnings | Proactive warnings when pinned version becomes significantly outdated (>30 days old) | LOW | Prevents security risks from forgotten pins. Weekly reminders after grace period |
| Fail-continue pattern | Update failures show warning but never block CLI operation | LOW | Field reliability - CLI must work even when version management fails |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Automatic silent updates | "Just keep me updated automatically" - users want convenience | Users lose control, surprise breaking changes, network usage spikes, security risks from unvetted updates | Notify + easy upgrade path. User confirms with `mc-update mc latest` |
| Real-time update notifications | "Tell me instantly when new version released" | Interrupts workflow, increases API traffic, most updates aren't urgent | Daily check is sufficient. Critical security updates can be communicated via GitHub |
| Forced updates | "Make everyone use latest version for support" | Breaks workflows mid-task, causes resentment, emergency rollback complexity | Allow pins with warnings. Document support policy separately |
| Complex version constraints | "Support semver ranges like >=2.0,<3.0" | Adds cognitive load, rarely used correctly, conflicts with pin/latest binary choice | Simple model: latest, pinned version, or list to choose from |
| Automatic rollback on failure | "If update breaks, auto-rollback" | Requires complex state tracking, hidden failures, user confusion about current state | Fail-continue: show warning, keep working on current version, user manually fixes |
| Update scheduling/cron | "Update automatically at 2am" | Requires daemon/background process, platform-specific scheduling, overkill for CLI | Opportunistic updates on next CLI invocation (lazy update pattern) |
| Progress bars for version checks | "Show me download progress for version check" | Version API calls are <1KB, progress bar adds visual noise for instant operation | Reserve progress bars for actual artifact downloads (container pulls, CLI upgrades) |
| Interactive update prompts | "Prompt Y/N when update available" | Blocks scripts/automation, breaks non-interactive use, violates UNIX philosophy | Banner notification + explicit upgrade command. Never block on user input |
| Multiple version installed | "Keep v1.x and v2.x both installed" | Path management nightmare, state isolation issues, config file conflicts | Use containers/venvs if multiple versions needed. CLI should be single-version |
| Pre-release/beta channel | "Let me opt into beta versions" | Support burden, bug reports from unstable versions, version confusion | Use git install for bleeding edge: `uv tool install git+https://...@main` |

## Feature Dependencies

```
[Background Version Check]
    └──requires──> [Timestamp-based Throttling]
    └──requires──> [Graceful Network Failure]
    └──requires──> [Version Source Authority]

[Update Notifications]
    └──requires──> [Background Version Check]
    └──enhances──> [Smart Update Notifications with Context]

[Version Pinning]
    └──requires──> [TOML Config Persistence]
    └──enhances──> [Stale Pin Warnings]
    └──enhances──> [Grace Period Suppression]

[mc-update Utility]
    └──requires──> [Version Listing with Metadata]
    └──requires──> [Version Pinning]
    └──requires──> [Manual Update Trigger]

[Container Auto-Pull]
    └──requires──> [Background Version Check]
    └──requires──> [Version Pinning]
    └──conflicts──> [Running Containers] (do not update images with active containers)

[Dual-Artifact Management]
    └──requires──> [Container Auto-Pull]
    └──requires──> [mc-update Utility]
```

### Dependency Notes

- **Background Version Check requires Timestamp-based Throttling:** Without throttling, every CLI invocation would hit GitHub/Quay APIs, causing rate limits and slow startup
- **Update Notifications require Background Version Check:** Can't notify about updates without checking for them first
- **Version Pinning requires TOML Config Persistence:** Pins must survive CLI restarts and system reboots
- **Container Auto-Pull conflicts with Running Containers:** Podman best practice - don't pull images while containers are running from them. Check container state before auto-pull
- **Dual-Artifact Management requires both systems:** CLI version management and container version management must work independently before coordinating them

## MVP Definition

### Launch With (v2.0.4)

Minimum viable product — what's needed to validate the concept.

- [x] **Background version checking with hourly throttle** — Core functionality, prevents API abuse
- [x] **Update notifications as banners** — User awareness of updates
- [x] **Version pinning with TOML persistence** — User control over update timing
- [x] **mc-update utility with list/pin commands** — Manual version management
- [x] **Graceful failure handling** — CLI must work even when version checks fail
- [x] **GitHub Releases API integration** — Authoritative CLI version source
- [x] **Quay.io registry API integration** — Authoritative container image source

### Add After Validation (v2.0.5+)

Features to add once core is working.

- [ ] **Stale pin warnings with grace period** — Trigger: users forget pins for >30 days
- [ ] **Smart notification context** — Trigger: basic notifications working but not actionable enough
- [ ] **Container auto-pull with pin respect** — Trigger: users manually pulling images too often
- [ ] **Version listing with release dates** — Trigger: users can't decide which version to pin

### Future Consideration (v3.0+)

Features to defer until product-market fit is established.

- [ ] **Changelog integration** — Show what's new in each version. Defer: can link to GitHub releases
- [ ] **Notification theming** — Color/format customization. Defer: rich library defaults sufficient
- [ ] **Update analytics** — Track update adoption rates. Defer: no telemetry infrastructure
- [ ] **Multi-registry support** — Alternative container registries. Defer: Quay.io sufficient
- [ ] **Offline mode detection** — Smart network detection. Defer: timeout-based detection works

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Background version checking | HIGH | MEDIUM | P1 |
| Update notifications | HIGH | LOW | P1 |
| Version pinning | HIGH | LOW | P1 |
| Graceful failure handling | HIGH | MEDIUM | P1 |
| mc-update utility | HIGH | MEDIUM | P1 |
| Timestamp-based throttling | HIGH | MEDIUM | P1 |
| Container auto-pull | MEDIUM | HIGH | P2 |
| Stale pin warnings | MEDIUM | LOW | P2 |
| Smart notification context | MEDIUM | LOW | P2 |
| Version listing with metadata | MEDIUM | LOW | P2 |
| Grace period suppression | LOW | MEDIUM | P3 |
| Dual-artifact coordination | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (v2.0.4)
- P2: Should have, add when possible (v2.0.5)
- P3: Nice to have, future consideration (v3.0+)

## Competitor Feature Analysis

| Feature | GitHub CLI (gh) | Rustup | uv | Our Approach (MC CLI) |
|---------|-----------------|--------|----|-----------------------|
| **Update check frequency** | Every 24h on any command | Manual `rustup update` only | Manual `uv self update` | Hourly throttle + daily user notifications |
| **Notification method** | Banner on stderr | Silent (check-only mode shows report) | None (manual only) | Banner on stderr with context |
| **Disable notifications** | `GH_NO_UPDATE_NOTIFIER=1` | `rustup set auto-self-update disable` | N/A (no notifications) | TOML config + CLI flag |
| **Version pinning** | No (use package manager pins) | Toolchain pinning (different concept) | No (use package manager) | Built-in TOML-based pinning |
| **Graceful degradation** | Yes (continues on check failure) | Yes (offline-capable) | Yes | Yes (fail-continue pattern) |
| **Update command** | `gh upgrade` (but uses package manager) | `rustup update` | `uv self update` | `mc-update mc latest` (uses uv internally) |
| **Container versioning** | N/A | N/A | N/A | **Differentiator**: manage both CLI and container |
| **Auto-update** | No | Configurable (enable/check-only/disable) | No | No (notify + easy upgrade path) |
| **Version listing** | No | `rustup toolchain list` | `uv python list` | **Differentiator**: with dates and context |
| **Stale version warnings** | No | No | No | **Differentiator**: grace period + weekly reminders |

### Key Insights from Competitors

**GitHub CLI:**
- 24-hour check window prevents API spam
- Environment variable for suppression is simple and effective
- Uses package manager for actual upgrades (delegates responsibility)
- Notifications on stderr don't interfere with stdout (script-friendly)

**Rustup:**
- Three-mode system (disable/enable/check-only) offers good control
- `--no-self-update` flag for per-invocation control
- Manual-first philosophy - only checks when user runs `rustup update`
- Clear separation: `rustup update` for toolchains, `rustup self update` for rustup itself

**uv:**
- Self-update only works with standalone installer (security boundary)
- Different installation methods use different update mechanisms (Homebrew, Cargo, PyPI)
- No built-in notifications - relies on package manager patterns
- Clean separation: `uv self update` for uv, `uv tool upgrade` for tools

**MC CLI Synthesis:**
- Adopt GitHub CLI's 24h check + stderr notification pattern
- Adopt rustup's three-mode philosophy (disable/check-only/auto)
- Adopt uv's delegation to package manager for actual upgrades
- **Innovate:** Add version pinning (competitors lack this)
- **Innovate:** Add container image version coordination (unique to containerized CLIs)
- **Innovate:** Add stale pin warnings (safety net competitors lack)

## Update Timing Patterns

### Background Check Pattern (Adopted)

**How it works:**
1. Every CLI invocation checks if last version check was >1 hour ago
2. If yes, spawn async/background check to GitHub/Quay APIs
3. Cache results with timestamp
4. Next invocation reads cached results and displays notification if update available
5. Version check never blocks command execution

**Advantages:**
- No user-facing latency (checks happen in background)
- Respects API rate limits (hourly throttle)
- Cached results available even when offline
- Simple implementation (timestamp comparison)

**Disadvantages:**
- First invocation after update won't show notification (delay until next invocation)
- Requires persistent storage for cache and timestamp

**Used by:** GitHub CLI (24h window), many Homebrew formulae

### Opportunistic Update Pattern (Rejected)

**How it works:**
1. On CLI invocation, check if update available
2. If yes, download and apply update before running command
3. Then execute user's command

**Why rejected:**
- Blocks command execution (violates non-blocking requirement)
- Surprises users with unexpected delays
- Can break scripts/automation
- Network failures block CLI usage

**Used by:** Some mobile apps, Windows updates (poorly received)

### Scheduled Update Pattern (Rejected)

**How it works:**
1. Install systemd timer/cron job/launchd plist
2. Run update check on schedule (e.g., daily at 2am)
3. CLI reads results from scheduled job

**Why rejected:**
- Requires daemon/background service (complexity)
- Platform-specific implementation (macOS launchd, Linux systemd, Windows Task Scheduler)
- Installation complexity (user must enable service)
- Overkill for CLI tool (background check pattern simpler)

**Used by:** System package managers (apt, yum), enterprise software

### On-Demand Only Pattern (Considered)

**How it works:**
1. No automatic checks
2. User runs `mc-update check` to see if update available
3. User runs `mc-update mc latest` to upgrade

**Why considered:**
- Simple implementation
- No background checks or caching needed
- User has full control

**Why not adopted:**
- Users won't check regularly (leads to outdated installations)
- Misses security updates
- Inferior UX compared to automatic notifications

**Used by:** Older CLI tools, minimal shells

## Update UX Patterns

### Banner Notification Pattern (Adopted)

**Visual example:**
```
┌────────────────────────────────────────────────────────────────┐
│ Update available: v2.0.5 (released 2026-02-10)                 │
│ You're running: v2.0.4                                          │
│ Run: mc-update mc latest                                        │
└────────────────────────────────────────────────────────────────┘
```

**Characteristics:**
- Appears at top of output (before command execution)
- Uses box drawing characters (rich library)
- Shows current version, new version, and upgrade command
- Dismisses automatically (shown once per session)
- Never blocks command execution

**Advantages:**
- High visibility without being intrusive
- Actionable (tells user exactly what to do)
- Script-friendly (on stderr, doesn't pollute stdout)
- Accessible (plain text, no colors required)

**Used by:** GitHub CLI, Homebrew, npm

### Status Line Pattern (Considered)

**Visual example:**
```
mc v2.0.4 (update available: v2.0.5) | mc case 12345678
```

**Why considered:**
- Subtle, non-intrusive
- Always visible
- Doesn't add extra lines

**Why not adopted:**
- Easy to miss
- Doesn't provide upgrade command
- Less actionable than banner
- Clutters primary output

**Used by:** Git status, some shells

### Interactive Prompt Pattern (Rejected)

**Visual example:**
```
Update available: v2.0.5. Update now? [Y/n]
```

**Why rejected:**
- Blocks command execution
- Breaks non-interactive use (scripts, CI/CD)
- Violates UNIX philosophy (tools should compose)
- Annoying for frequent CLI users

**Used by:** Windows software installers (anti-pattern for CLI)

### Silent Background Update Pattern (Rejected)

**How it works:**
- Update happens silently in background
- User never sees notification
- Next CLI invocation uses new version

**Why rejected:**
- Breaks user trust (surprise changes)
- Can introduce breaking changes mid-workflow
- Security risk (unvetted updates)
- Violates principle of least surprise

**Used by:** Chrome browser (controversial), some Electron apps

## Pinning Patterns

### Binary Pin Pattern (Adopted)

**How it works:**
- Pin to specific version: `mc-update pin mc 2.0.4`
- Unpin to track latest: `mc-update unpin mc`
- Two states: pinned or unpinned (no ranges)

**Advantages:**
- Simple mental model (pinned = this version, unpinned = latest)
- Easy to implement
- Clear intent

**Disadvantages:**
- No semver range support (can't say ">=2.0,<3.0")

**Rationale:**
- CLI tools rarely need range constraints
- Simplicity reduces cognitive load
- Power users can use git refs for bleeding edge

**Used by:** Most version pinning systems in simplified form

### Semver Range Pattern (Rejected)

**How it works:**
- Pin to range: `mc-update pin mc ">=2.0.4,<3.0"`
- Solver picks latest in range

**Why rejected:**
- Complex to implement (need semver parser and solver)
- Complex to explain to users
- Rarely needed for CLI tools
- Edge cases (pre-release versions, build metadata)

**Used by:** Package managers (npm, cargo, poetry) where needed

### Lock File Pattern (Considered)

**How it works:**
- Store exact versions in lock file (like package-lock.json)
- Commit lock file to version control
- Reproducible environments

**Why considered:**
- Guarantees reproducibility
- Works well in team environments

**Why not adopted:**
- MC CLI is end-user tool, not library
- Not distributed in teams (single-user install)
- TOML config sufficient for user preferences

**Used by:** Package managers (npm, poetry, cargo)

### Pin with Grace Period Pattern (Adopted - Differentiator)

**How it works:**
1. User pins to version: `mc-update pin mc 2.0.4`
2. Pin timestamp stored in TOML
3. For first 30 days, no stale warnings shown
4. After 30 days, weekly warnings: "Pinned version is 45 days old, consider upgrading"
5. User can suppress warnings or unpin

**Advantages:**
- Respects intentional pins (no immediate nagging)
- Prevents forgotten pins (safety net)
- Balances control with safety

**Disadvantages:**
- More complex than simple pin
- Requires timestamp tracking

**Rationale:**
- Best of both worlds: user control + safety net
- Addresses "pin and forget" anti-pattern
- Unique differentiator (competitors don't have this)

**Used by:** None (MC CLI innovation)

## Graceful Degradation Patterns

### Fail-Continue Pattern (Adopted)

**How it works:**
1. Attempt version check API call
2. If success: cache results, continue
3. If failure: log warning, use stale cache if available, continue
4. Never block CLI operation due to version check failure

**Example:**
```
Warning: Unable to check for updates (network timeout). Using cached data.
[command executes normally]
```

**Advantages:**
- CLI remains functional offline
- Network failures don't break workflows
- Degrades gracefully

**Used by:** GitHub CLI, most well-designed CLI tools

### Circuit Breaker Pattern (Considered)

**How it works:**
1. Track failure rate for version checks
2. If >3 consecutive failures, "open circuit" (stop checking for 24h)
3. After cooldown, try again

**Why considered:**
- Prevents repeated failures from slowing CLI
- Reduces API load during outages

**Why not adopted:**
- Overkill for version checks (simple timeout sufficient)
- Hourly throttle already limits impact
- Adds complexity

**Used by:** Microservices, high-traffic systems

### Stale Cache Fallback Pattern (Adopted)

**How it works:**
1. Attempt fresh version check
2. If failure and cache exists: use stale cache, show warning
3. If failure and no cache: show warning, continue without version info

**Example:**
```
Warning: Version check failed. Last checked 3 days ago.
[command executes normally]
```

**Advantages:**
- Better than nothing (stale data > no data)
- User aware of staleness
- No blocking

**Used by:** DNS resolvers, CDNs, distributed caches

## Existing MC CLI Integration Points

### TOML Configuration System (Already Built)

**Location:** `~/mc/config/config.toml`

**Current structure:**
```toml
[mc]
base_directory = "~/mc"
# Auto-update settings will extend this
```

**Auto-update additions:**
```toml
[mc.updates]
check_enabled = true
last_check_timestamp = 1707696000
notification_suppressed_until = 0

[mc.versions]
cli_pinned = "2.0.4"
cli_pinned_timestamp = 1707696000
container_pinned = "1.0.0"
container_pinned_timestamp = 1707696000
```

**Advantages:**
- Already using platformdirs for XDG paths
- tomli-w already in dependencies for writing TOML
- Users familiar with TOML config location

### Container System (Already Built)

**Current capabilities:**
- Podman integration via podman-py library
- Container lifecycle management
- Independent versioning (container 1.0.0 vs CLI 2.0.4)

**Auto-update integration:**
- Check Quay.io for new container versions
- Pull new images when available (unless pinned)
- Warning when running stale pinned container

**Constraint:**
- Don't pull images while containers running from them
- Check `podman ps` before auto-pull

### Rich Library (Already Built)

**Current usage:**
- Progress bars for downloads
- Structured console output
- Table formatting

**Auto-update additions:**
- Banner notifications (Panel component)
- Version listing tables (Table component)
- Styled warnings (Text with markup)

**Example:**
```python
from rich.console import Console
from rich.panel import Panel

console = Console()
console.print(Panel(
    "Update available: v2.0.5\nRun: mc-update mc latest",
    title="MC CLI Update",
    border_style="yellow"
))
```

### Existing Cache System (Already Built)

**Current implementation:**
- Case metadata cache with TTL (5 minutes)
- SQLite-based storage
- Located in `~/mc/config/cache/`

**Auto-update reuse:**
- Version check cache (hourly TTL)
- Same cache directory structure
- Similar timestamp-based invalidation

**Schema addition:**
```sql
CREATE TABLE version_cache (
    artifact TEXT PRIMARY KEY,  -- 'cli' or 'container'
    latest_version TEXT,
    checked_at TIMESTAMP,
    check_successful BOOLEAN
);
```

## Sources

**CLI Update Patterns:**
- [Rustup Basic Usage](https://rust-lang.github.io/rustup/basics.html) - Update mechanisms and self-update configuration
- [GitHub CLI Environment Variables](https://cli.github.com/manual/gh_help_environment) - Update notification control (GH_NO_UPDATE_NOTIFIER)
- [uv Tool Management](https://docs.astral.sh/uv/guides/tools/) - Tool installation and upgrade patterns
- [How to upgrade uv](https://pydevtools.com/handbook/how-to/how-to-upgrade-uv/) - Self-update patterns for different installation methods

**Version Pinning and Lock Files:**
- [Dependency Management With Python Poetry](https://realpython.com/dependency-management-python-poetry/) - Lock file patterns
- [Lockfiles Pantsbuild](https://www.pantsbuild.org/dev/docs/python/overview/lockfiles) - Pinning mechanisms

**Background Check and Throttling:**
- [How to Implement Background Tasks in FastAPI](https://oneuptime.com/blog/post/2026-02-02-fastapi-background-tasks/view) - Async background patterns
- [How to Implement Async Processing Patterns](https://oneuptime.com/blog/post/2026-01-25-implement-async-processing-patterns/view) - Async processing patterns

**Graceful Degradation:**
- [Building Resilient REST API Integrations](https://medium.com/@oshiryaeva/building-resilient-rest-api-integrations-graceful-degradation-and-combining-patterns-e8352d8e29c0) - Graceful degradation patterns
- [AWS Reliability Pillar: Graceful Degradation](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html) - Transform hard dependencies into soft dependencies

**Container Auto-Update:**
- [Podman Auto-Update Documentation](https://docs.podman.io/en/latest/markdown/podman-auto-update.1.html) - Container auto-update patterns
- [How to use auto-updates and rollbacks in Podman](https://www.redhat.com/en/blog/podman-auto-updates-rollbacks) - Auto-update and rollback patterns

**Notification UX:**
- [Carbon Design System: Notification Pattern](https://carbondesignsystem.com/patterns/notification-pattern/) - Notification banner UX guidelines
- [Notification Banner - Astro UX Design System](https://www.astrouxds.com/components/notification-banner/) - Banner design patterns
- [Website Notification Banner: Best Examples, Use Cases, and UX Tips](https://userguiding.com/blog/website-notification-banner) - Banner best practices

**Registry APIs:**
- [Quay.io API Documentation](https://docs.quay.io/api/) - Container registry API for version checking
- [Working with tags - Quay Documentation](https://docs.quay.io/guides/tag-operations.html) - Tag operations

---
*Feature research for: MC CLI Auto-Update System*
*Researched: 2026-02-11*
*Confidence: HIGH (verified with official documentation and multiple authoritative sources)*
