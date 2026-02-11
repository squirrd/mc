# Project Research Summary

**Project:** MC CLI Auto-Update and Version Management
**Domain:** CLI tool version management with dual-artifact coordination (CLI + container)
**Researched:** 2026-02-11
**Confidence:** HIGH

## Executive Summary

MC CLI requires a sophisticated auto-update system that manages both the CLI tool itself (distributed via uv/PyPI) and container images (hosted on Quay.io). Expert implementations in this domain emphasize non-blocking version checks with aggressive throttling, graceful degradation when APIs are unavailable, and explicit user control over update timing through version pinning. The recommended approach leverages MC's existing infrastructure (TOML config, Rich terminal output, requests library, platformdirs) and adds only one new dependency: the `packaging` library for PEP 440-compliant version comparison.

The critical architectural principle is separation of concerns: version checking must never block CLI operations. Background checks with hourly throttling, ETag-based conditional requests to prevent GitHub API rate limiting (60 req/hour unauthenticated), and stale-while-revalidate caching ensure the CLI remains responsive even when networks are slow or registries are down. The update execution mechanism delegates to uv's battle-tested `tool upgrade` command rather than attempting in-place self-updates, avoiding the platform-specific complexity and failure modes that plague custom update systems.

Key risks center on race conditions (concurrent config writes corrupting TOML files), version comparison bugs (infinite update loops), and notification fatigue (users training to ignore update banners). These are mitigated through file locking, semantic versioning via the `packaging` library, and notification suppression (maximum once per day per version). The dual-artifact nature introduces unique challenges around container lifecycle awareness—users must understand that pulling a new image doesn't update running containers—requiring clear messaging and version mismatch indicators in container listings.

## Key Findings

### Recommended Stack

MC CLI's existing stack provides nearly everything needed for auto-update functionality. The only required addition is the `packaging` library (>=24.0) for PEP 440-compliant version comparison. Recent performance improvements in packaging v26.0 (January 2026) deliver 2-5x faster version parsing, making it ideal for frequent background checks.

**Core technologies:**
- `packaging>=24.0`: PEP 440 version comparison and parsing — de facto standard for Python versioning, handles pre-releases/post-releases/epochs correctly, 3x performance improvement in v26.0
- `requests>=2.31.0`: GitHub/Quay.io API calls — already present, handles both JSON APIs and supports ETag conditional requests for rate limit management
- `tomli_w>=1.0.0`: TOML config persistence — already present, safe serialization for version pins and timestamps
- `platformdirs>=4.0.0`: Cross-platform cache paths — already present, provides XDG-compliant cache directory for throttle timestamps
- `rich>=14.0.0`: Update notification banners — already present, Panel component perfect for non-intrusive update notifications

**Integration with uv:**
- Delegate upgrade execution to `uv tool upgrade mc-cli` (atomic updates, proper dependency resolution)
- Delegate pinning to `uv tool install mc-cli==X.Y.Z` (explicit version installation)
- No custom download/install logic needed (uv handles complexity)

### Expected Features

Research reveals a clear hierarchy of user expectations based on how established CLI tools (GitHub CLI, rustup, uv) handle updates.

**Must have (table stakes):**
- Background version checking with throttling — users expect tools to know about updates without manual checking
- Update availability notifications — silence means "checked and current," not "haven't checked"
- Manual update trigger — explicit command to upgrade (trust but verify, not automatic)
- Graceful network failure — CLI must work offline or when APIs are down
- Timestamp-based throttling — prevents API hammering, respects rate limits (hourly for background, daily for notifications)
- Current version indicator — when listing versions, mark which is installed

**Should have (competitive advantage):**
- Version pinning with grace period — pin + suppress warnings for 30 days, then weekly reminders (unique to MC)
- Dual-artifact version management — manage both CLI and container from single utility (unique to containerized CLIs)
- Smart notifications with context — not just "update available" but "pinned to v2.0.4 (30 days old), run mc-update to unpin"
- Container auto-pull with pin respect — automatically pull new images unless pinned, warn when running stale version
- Unified update utility — single `mc-update` command for CLI upgrades, container pulls, version listing, pinning
- Stale pin warnings — proactive warnings when pinned version becomes outdated (>30 days old)

**Defer (v2+):**
- Changelog integration — show what's new in each version (can link to GitHub releases initially)
- Update analytics — track update adoption rates (no telemetry infrastructure currently)
- Multi-registry support — alternative container registries (Quay.io sufficient for v1)
- Pre-release/beta channels — opt into unstable versions (use git install for bleeding edge)

### Architecture Approach

The standard architecture for CLI auto-update systems follows a layered approach with strict separation between version checking (non-blocking, background) and update execution (explicit, user-triggered). MC's implementation should hook into the existing CLI entry point immediately after logging setup but before config load, ensuring version checks run on every invocation without blocking command execution.

**Major components:**
1. **VersionChecker** (utils/version_checker.py) — Query GitHub/Quay APIs, parse responses, compare versions using packaging.version.Version, handle rate limiting with ETag conditional requests, implement hourly throttle with timestamp cache
2. **ConfigExtension** (config/models.py) — Extend existing schema with version_management section containing pinned_mc_version, pinned_container_version, last_version_check timestamp, available versions cache
3. **UpdateBanner** (utils/update_banner.py) — Display Rich Panel notifications at command completion (non-intrusive), show actionable commands, suppress duplicate notifications (once per day per version)
4. **mc-update CLI** (cli/update.py) — Separate console_scripts entry point that survives package upgrades, executes subprocess(['uv', 'tool', 'upgrade', 'mc-cli']), validates post-upgrade, provides recovery instructions on failure

**Critical patterns:**
- **Non-blocking checks:** Throttle to 1 check/hour, fail silently on network errors, never block command execution
- **ETag caching:** Use If-None-Match headers to get HTTP 304 Not Modified responses (saves API quota, doesn't count against rate limit)
- **File locking:** Use filelock library for atomic config writes to prevent corruption from concurrent mc processes
- **Stale-while-revalidate:** Return cached version immediately, trigger background revalidation if cache older than 1 hour

### Critical Pitfalls

Research identified 10 critical pitfalls with detailed prevention strategies. The top 5 most dangerous:

1. **Synchronous version check blocking startup** — Version checks on every invocation blocking command execution. Prevention: hourly throttle + async background checks + aggressive 2s timeout + fail silently. Must address in Phase 1 or retrofitting is high-cost.

2. **GitHub API rate limiting without fallback** — Unauthenticated API has 60 req/hour limit, easily exhausted by multiple users or CI/CD. Prevention: ETag conditional requests (304 Not Modified doesn't count against limit), cache x-ratelimit headers, exponential backoff on 429, graceful degradation to cached data. Must address in Phase 1.

3. **uv tool upgrade failure leaving broken installation** — Partial upgrade leaves tool unusable. Prevention: health check before upgrade (uv tool list --outdated), validation after (mc --version), recovery instructions on failure (uv tool install --force mc-cli), never upgrade while tool is running (Windows file locks).

4. **Concurrent config file writes causing corruption** — Multiple mc processes updating TOML simultaneously corrupt file. Prevention: filelock library + atomic write pattern (temp file + rename), SQLite for frequently-changing state, separate throttle cache from main config. Must address in Phase 1.

5. **Infinite update loop from version comparison bug** — String comparison instead of semantic versioning causes "2.0.10" < "2.0.9" bugs. Prevention: use packaging.version.Version for all comparisons, test edge cases (pre-releases, multi-digit versions), store last_offered_version to detect loops. Must address in Phase 1.

## Implications for Roadmap

Based on research, the implementation should follow a 3-phase structure that builds foundation first (non-blocking checks, correct version comparison, file locking), then adds update mechanics (uv integration, validation), and finally polishes UX (notification tuning, container lifecycle awareness).

### Phase 1: Version Check Infrastructure
**Rationale:** Foundation for all version management features. Version checking, throttling, and config safety must be correct before building anything on top. Retrofitting non-blocking architecture or fixing version comparison bugs is expensive.

**Delivers:** Background version checking with hourly throttle, GitHub Releases API integration with ETag support, TOML config extension with file locking, version comparison using packaging library, notification suppression (once per day per version).

**Addresses features:**
- Background version checking (table stakes)
- Timestamp-based throttling (table stakes)
- Graceful network failure (table stakes)

**Avoids pitfalls:**
- Synchronous version check blocking startup (critical)
- GitHub API rate limiting without fallback (critical)
- Concurrent config file writes causing corruption (critical)
- Infinite update loop from version comparison bug (critical)

**Stack elements:**
- packaging library for PEP 440 version comparison
- requests for GitHub API with ETag headers
- tomli_w + filelock for safe config writes
- platformdirs for cache directory

**Technical details:**
- Hook into cli/main.py after logging setup
- Implement should_check_version() with 1-hour throttle
- Store last_check timestamp in separate cache file (not main config)
- Use packaging.version.Version for all comparisons
- Implement ETag conditional requests (If-None-Match header)
- File locking for all config writes

### Phase 2: Auto-Update Mechanics
**Rationale:** With version checking working reliably, add the ability to actually upgrade. Update execution has complex failure modes (broken installations, version mismatches) that require careful validation and recovery mechanisms.

**Delivers:** mc-update CLI utility as separate console_scripts entry, uv tool upgrade integration with pre-flight checks, post-upgrade validation, version pinning (binary: pinned or latest), Quay.io API integration for container version checking.

**Addresses features:**
- Manual update trigger (table stakes)
- Version pinning with TOML persistence (differentiator)
- Container auto-pull preparation (foundation for Phase 3)

**Avoids pitfalls:**
- uv tool upgrade failure leaving broken installation (critical)
- Version pinning without escape hatch (after 30 days, show warnings)

**Architecture components:**
- cli/update.py with separate entry point (survives package upgrades)
- Pre-flight checks: uv installed, network accessible, no active sessions
- Post-upgrade validation: run mc --version, check exit code
- Recovery instructions on failure

**Technical details:**
- subprocess.run(['uv', 'tool', 'upgrade', 'mc-cli'], check=True)
- Pin support: subprocess.run(['uv', 'tool', 'install', f'mc-cli=={version}'])
- Store pinned_mc_version in config with pin_timestamp
- Quay.io Docker Registry v2 API: /v2/{namespace}/{repo}/tags/list
- Filter tags with packaging.version.Version (skip "latest", "stable")

### Phase 3: UX Refinement and Container Integration
**Rationale:** Core functionality (checking, upgrading) is stable. Now add polish: smart notifications with context, container lifecycle awareness, stale pin warnings. These improve UX without risking core stability.

**Delivers:** Smart update notifications with context (pinned version age, versions behind), container auto-pull with pin respect, version listing with release dates and metadata, container version mismatch indicators in mc container list, stale pin warnings (30-day grace period + weekly reminders).

**Addresses features:**
- Smart notification context (differentiator)
- Dual-artifact version management (differentiator)
- Stale pin warnings (differentiator)
- Version listing with metadata (differentiator)

**Avoids pitfalls:**
- Update notification spam training users to ignore (show max once per day)
- Running container not updated but user expects it (clear messaging)

**Architecture components:**
- Enhanced update_banner.py with rich context
- Container lifecycle awareness in container list output
- Pin age calculation and warning logic

**Technical details:**
- Calculate pin age: datetime.now(UTC) - pin_timestamp
- Show warnings after 30 days, weekly reminders after 60 days
- Container list shows: CASE | STATUS | IMAGE | AVAILABLE (with mismatch indicator)
- Notification context: "Pinned to 2.0.4 (45 days ago), latest: 2.0.9 (security fixes)"

### Phase Ordering Rationale

- **Phase 1 first:** Version checking is the foundation. Non-blocking architecture, correct version comparison, and file locking must be right from the start. Retrofitting these is expensive and risky. All other phases depend on reliable version checking.

- **Phase 2 second:** Update mechanics build on stable version checking. Validation and recovery mechanisms require careful testing. Separating from Phase 1 allows thorough testing of version checking before introducing update execution complexity.

- **Phase 3 last:** UX refinements are valuable but not critical. Can iterate on notification wording, container messaging, and pin warnings without affecting core functionality. Allows real-world feedback from Phase 1-2 to inform UX decisions.

**Dependency chain:**
- Phase 3 depends on Phase 2 (needs working pin system for stale warnings)
- Phase 2 depends on Phase 1 (needs reliable version checking before executing upgrades)
- Phase 1 is foundational (no dependencies)

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2: Auto-Update Mechanics** — Reason: uv tool upgrade failure modes are complex (Python version mismatches, Windows file locking, partial installs). Needs research on recovery strategies and validation approaches. Research found diverse failure modes but limited documentation on detection/recovery.

- **Phase 3: Container Integration** — Reason: Interaction between container auto-pull and existing ContainerManager is unclear. Needs research on podman-py integration, image pull timing (don't pull while containers running), and state management (which image version is each container using).

**Phases with standard patterns (skip research-phase):**
- **Phase 1: Version Check Infrastructure** — Reason: Well-documented patterns. GitHub CLI, rustup, and multiple Python tools (check4updates, update-checker) provide clear implementation examples. ETag usage, throttling strategies, and file locking are established patterns with abundant documentation.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommended technologies verified via official documentation. Packaging library is Python standard (used by pip/setuptools). Existing stack (requests, tomli_w, platformdirs, rich) already present in MC. Only new dependency is packaging. |
| Features | HIGH | Feature expectations validated across multiple established CLIs (GitHub CLI, rustup, uv). Table stakes features consistent across all three. Differentiators (dual-artifact management, pin grace period) are novel but low-risk additions. |
| Architecture | HIGH | Standard patterns documented in multiple authoritative sources (Salesforce CLI, Azure CLI, check4updates library). Non-blocking check pattern proven in GitHub CLI (24-hour window). Separation of version checking from update execution is industry standard. |
| Pitfalls | HIGH | All critical pitfalls documented with real-world examples. GitHub API rate limiting has official documentation. uv upgrade failure modes documented in uv issue tracker. Version comparison bugs have established solutions (packaging library). File locking patterns well-documented. |

**Overall confidence:** HIGH

Research drew from official documentation (GitHub API docs, uv docs, packaging docs, Quay.io API docs), established open-source implementations (GitHub CLI, rustup), and Python-specific libraries (check4updates, update-checker) with proven track records. All critical pitfalls have documented prevention strategies with code examples.

### Gaps to Address

Remaining uncertainties to resolve during implementation:

- **uv installation detection:** Research assumes checking if `uv` binary exists in PATH. Unclear: should mc-update support pip-based upgrades if user installed via pip instead of uv? How to detect installation method reliably? Resolution: Start with uv-only support, document that mc-update requires uv installation. Can add pip support in v2.1 if users request it.

- **Container version pinning integration:** Config schema includes `pinned_container_version` but interaction with existing ContainerManager is undefined. Which component enforces pin during container start? How to show version mismatch in container listings? Resolution: Phase 2 planning should map container pin enforcement into existing container lifecycle. Likely: check pin in container_start() before podman.images.pull().

- **ETag storage location:** Should ETag be stored in config.toml or separate cache file? Config write contention vs. cache coherence tradeoff. Resolution: Store in separate cache file (~/.cache/mc/version_check.json) alongside last_check timestamp. Reduces config write frequency, allows cache clearing without losing pins.

- **Notification display timing:** Show banner at start of command (high visibility, may disrupt output) or end of command (less intrusive, may be missed)? Resolution: Test both during Phase 3 UX refinement. GitHub CLI shows at end (less disruptive). Consider: show at start for major versions, at end for patches.

## Sources

### Primary (HIGH confidence)
- [PEP 440 – Version Identification and Dependency Specification](https://peps.python.org/pep-0440/) — Official Python versioning standard
- [GitHub REST API - Releases](https://docs.github.com/en/rest/releases/releases) — Official API documentation for version checking
- [GitHub Docs: Rate Limits for REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) — Rate limiting and ETag conditional requests
- [uv Tool Management](https://docs.astral.sh/uv/guides/tools/) — Official uv documentation for tool upgrade mechanics
- [Quay.io API Documentation](https://docs.quay.io/api/) — Official container registry API
- [Docker Registry v2 API](https://docs.docker.com/registry/spec/api/) — Standard for /v2/.../tags/list endpoint
- [packaging library documentation](https://packaging.pypa.io/en/stable/version.html) — PEP 440 version comparison implementation
- [Rich library documentation](https://rich.readthedocs.io/en/stable/) — Panel component for update banners

### Secondary (MEDIUM confidence)
- [GitHub CLI source code](https://github.com/cli/cli) — Real-world implementation of 24-hour version check pattern
- [Rustup documentation](https://rust-lang.github.io/rustup/) — Auto-update configuration patterns
- [check4updates Python library](https://github.com/MatthewReid854/check4updates) — Reusable version check implementation
- [update-checker Python module](https://github.com/bboe/update_checker) — PyPI version checking patterns
- [filelock library](https://pypi.org/project/filelock/) — File locking for concurrent config writes
- [How we made Python's packaging library 3x faster](https://iscinumpy.dev/post/packaging-faster/) — Performance improvements in v26.0

### Tertiary (LOW confidence, needs validation)
- uv GitHub issues (#8028, #11534, #11930, #8528) — Upgrade failure modes and recovery strategies (anecdotal but informative)
- [Quay.io rate limiting](https://access.redhat.com/solutions/6218921) — Community reports of "few requests per second" limit (not officially documented)

---
*Research completed: 2026-02-11*
*Ready for roadmap: yes*
