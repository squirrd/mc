---
phase: 33-container-setup
plan: 01
subsystem: infra
tags: [containerfile, claude-code, nodejs, npm, multi-stage-build, podman]

# Dependency graph
requires:
  - phase: 32-oc-downloader
    provides: oc-downloader stage pattern used as reference for new stage placement
provides:
  - claude-downloader Containerfile stage (Stage 3) installing @anthropic-ai/claude-code@2.1.80
  - claude binary and node_modules available in final container image
  - nodejs runtime installed in final stage for claude CLI execution
affects:
  - 33-02-container-setup (config and auth mounts — depends on claude being in the image)
  - container build pipeline

# Tech tracking
tech-stack:
  added: ["@anthropic-ai/claude-code@2.1.80", "nodejs (runtime in final stage)"]
  patterns: ["multi-stage Containerfile isolation: dedicated stage per tool installer"]

key-files:
  created: []
  modified: ["container/Containerfile"]

key-decisions:
  - "CLAUDE_VERSION ARG declared inside claude-downloader stage (not global), consistent with OCM_VERSION and BACKPLANE_VERSION patterns"
  - "Used full UBI (ubi10/ubi:10.1) not ubi-minimal for claude-downloader stage — needed for nodejs/npm via dnf"
  - "Both /usr/local/bin/claude and /usr/local/lib/node_modules/@anthropic-ai/claude-code copied — wrapper script requires node_modules"

patterns-established:
  - "Tool installer stages: each tool gets its own FROM stage, ARG inside that stage, binary extracted via COPY --from in final stage"

# Metrics
duration: 1min
completed: 2026-03-20
---

# Phase 33 Plan 01: Container Setup — Claude Code CLI Installer Summary

**claude-downloader Containerfile stage added: installs @anthropic-ai/claude-code@2.1.80 via npm, with nodejs runtime and both binary + node_modules copied into the final stage**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-20T10:30:07Z
- **Completed:** 2026-03-20T10:31:04Z
- **Tasks:** 3 (Tasks 1+2 committed together; Task 3 separate)
- **Files modified:** 1

## Accomplishments

- New `claude-downloader` stage (Stage 3) inserted after `backplane-downloader` — uses full UBI 10.1 for dnf nodejs/npm availability
- `ARG CLAUDE_VERSION=2.1.80` declared inside stage, pinned version follows existing pattern
- Final stage updated: `nodejs` added to runtime dnf install block, both claude artifacts copied via `COPY --from=claude-downloader`
- Stage comments renumbered: oc-downloader=4, mc-builder=5, final=6

## Task Commits

Each task was committed atomically:

1. **Tasks 1+2: Add CLAUDE_VERSION ARG and claude-downloader stage** - `8f10bbb` (feat)
2. **Task 3: Update final stage with nodejs and claude binary** - `4f00b3e` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `container/Containerfile` - Added claude-downloader stage (Stage 3), updated final stage with nodejs and COPY --from=claude-downloader lines, renumbered stage comments

## Decisions Made

- Tasks 1 and 2 committed together — CLAUDE_VERSION ARG only exists inside the new stage, making them a single atomic unit
- Used `ubi10/ubi:10.1` (full UBI) for claude-downloader since `ubi-minimal` does not have nodejs/npm in its dnf repos
- Both the binary (`/usr/local/bin/claude`) and package directory (`/usr/local/lib/node_modules/@anthropic-ai/claude-code`) are copied because the claude wrapper script references the node_modules path at runtime

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Containerfile has claude available — 33-02 can now add the mount flags for `~/mc/config` and `~/.claude` to the podman run invocation in the container launch code
- No blockers

---
*Phase: 33-container-setup*
*Completed: 2026-03-20*
