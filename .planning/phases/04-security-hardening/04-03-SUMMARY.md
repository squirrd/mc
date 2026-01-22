---
phase: 04-security-hardening
plan: 03
subsystem: security
tags: [bandit, security-scanning, linting, http-timeout]

# Dependency graph
requires:
  - phase: 04-01
    provides: "Token cache with secure file permissions"
  - phase: 04-02
    provides: "SSL verification enabled by default"
provides:
  - "Bandit security linter configured and passing"
  - "30-second HTTP timeout on all requests"
  - "Subprocess security annotations documented"
  - "Zero HIGH/MEDIUM severity security issues"
affects: [CI/CD pipeline integration, pre-commit hooks, security audit]

# Tech tracking
tech-stack:
  added: [bandit>=1.7.0]
  patterns:
    - "HTTP requests with 30-second timeout for DoS prevention"
    - "Security linter with HIGH severity threshold"
    - "nosec annotations with justifications for known-safe code"

key-files:
  created:
    - .bandit
    - .planning/phases/04-security-hardening/bandit-report.html
  modified:
    - pyproject.toml
    - src/mc/integrations/ldap.py
    - src/mc/integrations/redhat_api.py
    - src/mc/utils/auth.py

key-decisions:
  - "30-second HTTP timeout for all requests (prevents indefinite hangs)"
  - "HIGH severity threshold in Bandit config (prevents noise from low-priority warnings)"
  - "nosec annotations with detailed justifications (documents why code is safe)"
  - "Timeout prevents DoS vulnerability from slow/unresponsive servers"

patterns-established:
  - "HTTP timeout pattern: All requests.get/post/head calls include timeout=30"
  - "Security annotation pattern: nosec comments with detailed justifications explaining safety"
  - "HTML report generation for audit trail and detailed security analysis"

# Metrics
duration: 4min
completed: 2026-01-22
---

# Phase 04 Plan 03: Security Linting Summary

**Bandit security linter configured with zero HIGH/MEDIUM severity issues, 30-second HTTP timeouts preventing DoS, and documented subprocess safety**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-22T06:44:45Z
- **Completed:** 2026-01-22T06:48:54Z
- **Tasks:** 3
- **Files modified:** 4 (plus HTML report)

## Accomplishments
- Bandit 1.9.3 installed and configured with HIGH severity threshold
- Fixed 6 MEDIUM severity issues (B113 - requests without timeout)
- Added 30-second timeout to all HTTP requests (API calls, SSO auth, downloads)
- Documented subprocess safety with nosec annotations and justifications
- Generated HTML security audit report showing clean state

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Bandit dependency and configuration** - `566776a` (chore)
2. **Task 2: Run initial Bandit scan and document findings** - `2804539` (docs)
3. **Task 3: Address Bandit findings based on actual scan results** - `c8bea9b` (fix)

## Files Created/Modified

**Created:**
- `.bandit` - YAML configuration with HIGH severity threshold, excludes test/docs directories
- `.planning/phases/04-security-hardening/bandit-report.html` - Security audit report (updated after fixes)

**Modified:**
- `pyproject.toml` - Added bandit>=1.7.0 to dev dependencies, added [tool.bandit] section
- `src/mc/integrations/ldap.py` - Added nosec B602/B603/B607 annotations with justifications for subprocess calls
- `src/mc/integrations/redhat_api.py` - Added timeout=30 to 5 HTTP requests (GET/HEAD for cases/accounts/attachments/downloads)
- `src/mc/utils/auth.py` - Added timeout=30 to SSO token refresh POST request

## Decisions Made

**1. 30-second HTTP timeout for all requests**
- Prevents indefinite hangs on slow/unresponsive servers
- Mitigates DoS vulnerability from attacker-controlled slow responses
- Applied to all requests.get/post/head calls across codebase

**2. HIGH severity threshold in Bandit config**
- Prevents noise from LOW severity informational warnings
- Focuses on actionable security issues
- Config in both .bandit (YAML) and pyproject.toml for compatibility

**3. nosec annotations with detailed justifications**
- Documents WHY subprocess calls are safe (not just suppressing warnings)
- Explains validation (uid length 4-15 chars) and hardcoded command structure
- Helps future reviewers understand security decisions

**4. Fix MEDIUM issues, annotate LOW false positives**
- Fixed all 6 MEDIUM severity B113 (requests without timeout) issues
- Annotated LOW severity subprocess issues (B602/B603/B607) - known safe with validation
- Ignored B105 false positives ('Bearer' and empty string are not passwords)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - Bandit scan found expected issues (subprocess warnings, missing timeouts), all addressed as planned.

## Next Phase Readiness

**Security hardening phase completion:**
- Plan 04-01: Token cache with secure 0600 permissions
- Plan 04-02: SSL verification enabled, large file download safety checks
- Plan 04-03: Security linting with zero HIGH/MEDIUM issues, HTTP timeouts

**Ready for:**
- CI/CD integration: `bandit -c .bandit -r src/` in pre-commit or GitHub Actions
- Phase 5 (if exists): Security foundation complete, all critical vulnerabilities addressed
- Production deployment: Automated security scanning catches issues before merge

**Development workflow:**
- Run `bandit -c .bandit -r src/` before committing
- Review HTML report at `.planning/phases/04-security-hardening/bandit-report.html`
- Ensure no HIGH severity issues introduced

**Security posture:**
- 0 HIGH severity issues (down from 0)
- 0 MEDIUM severity issues (down from 6)
- 6 LOW severity issues remaining (informational/false positives, non-blocking)
- All HTTP requests protected against timeout-based DoS
- All subprocess calls documented as safe with justifications

---
*Phase: 04-security-hardening*
*Completed: 2026-01-22*
