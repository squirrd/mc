# Codebase Concerns

**Analysis Date:** 2026-01-20

## Tech Debt

**Hardcoded Base Directory:**
- Issue: Base directory path hardcoded to `/Users/dsquirre/Cases` in `src/mc/cli/main.py:13`
- Files: `src/mc/cli/main.py`
- Impact: Tool only works for one specific user; not portable across different systems or users
- Fix approach: Read from environment variable `MC_BASE_DIR` (already defined in `.env.example`) with sensible default like `~/Cases`

**Duplicate Environment Variable Checks:**
- Issue: `RH_API_OFFLINE_TOKEN` validation duplicated in both `src/mc/cli/main.py:21-24` and `src/mc/utils/auth.py:18-21`
- Files: `src/mc/cli/main.py`, `src/mc/utils/auth.py`
- Impact: Inconsistent error handling; double-check on every auth call; harder to maintain
- Fix approach: Remove check from main.py; let auth.py handle validation at point of use

**Version Synchronization Risk:**
- Issue: Version defined in both `src/mc/version.py:3` and `pyproject.toml:7`; `setup.py` reads from version.py using exec()
- Files: `src/mc/version.py`, `pyproject.toml`, `setup.py`
- Impact: Risk of version mismatch between files; exec() in setup.py is code smell
- Fix approach: Use single source of truth with setuptools_scm or importlib.metadata

**Incomplete Package Setup:**
- Issue: Both `setup.py` and `pyproject.toml` exist with different configurations; pyproject.toml lists dev dependencies but setup.py doesn't
- Files: `setup.py`, `pyproject.toml`
- Impact: Confusion about which is authoritative; pip install behavior may vary
- Fix approach: Migrate fully to pyproject.toml (modern standard), remove setup.py

**Typo in User-Facing Output:**
- Issue: Misspelling "dowloading attachemnts" in `src/mc/cli/commands/case.py:102`
- Files: `src/mc/cli/commands/case.py`
- Impact: Unprofessional output to users
- Fix approach: Fix typo to "downloading attachments"

## Known Bugs

**LDAP Search Command Inconsistent Flag:**
- Symptoms: `mc ls` command uses `-A` flag but the long form is `--All` (capitalized) in `src/mc/cli/main.py:51`
- Files: `src/mc/cli/main.py`
- Trigger: Running `mc ls uid --All` or checking help text
- Workaround: Use `-A` instead
- Fix: Change `--All` to `--all` (lowercase) for consistency with argparse conventions

**Status Typo in Output:**
- Symptoms: Output shows "CheckStaus" instead of "CheckStatus" in multiple places
- Files: `src/mc/controller/workspace.py:87`, `src/mc/cli/commands/case.py:125`
- Trigger: Running `mc check` or `mc create` commands
- Workaround: None needed, purely cosmetic
- Fix: Correct spelling to "CheckStatus"

## Security Considerations

**API Token Exposure Risk:**
- Risk: Offline token checked but access token not validated for expiration
- Files: `src/mc/utils/auth.py`
- Current mitigation: Token refresh happens on every invocation via POST to Red Hat SSO
- Recommendations: Add token caching with expiration check to avoid unnecessary SSO calls; validate token before use

**Missing HTTPS Verification:**
- Risk: No explicit verification of SSL certificates in requests calls
- Files: `src/mc/integrations/redhat_api.py`, `src/mc/utils/auth.py`
- Current mitigation: Requests library defaults to verify=True
- Recommendations: Explicitly set verify=True for clarity; consider certificate pinning for SSO endpoint

**Hardcoded Salesforce URL:**
- Risk: Internal Salesforce URL exposed in code at `src/mc/cli/commands/other.py:15`
- Files: `src/mc/cli/commands/other.py`
- Current mitigation: URL is to internal GSS system, requires authentication
- Recommendations: Move to configuration file if URL varies by environment

**No Input Validation on Case Numbers:**
- Risk: Case number passed directly to API without validation
- Files: `src/mc/cli/commands/case.py`, `src/mc/integrations/redhat_api.py`
- Current mitigation: API will reject invalid case numbers
- Recommendations: Add regex validation for case number format before API calls.  Validation should validate this "04349708" all should be numbers, and its a fixed length

**File Download Without Size Limits:**
- Note: Large files are expected in this use case; no size limits needed
- Files: `src/mc/integrations/redhat_api.py:75-91`
- Current state: Streams in 8KB chunks, no warnings
- Recommendations: Warn (not prompt) for files >3GB; implement parallel downloads with 4+ threads using ThreadPoolExecutor for better performance

## Performance Bottlenecks

**Sequential Attachment Downloads:**
- Problem: Attachments downloaded one at a time in `src/mc/cli/commands/case.py:39-49`
- Files: `src/mc/cli/commands/case.py`
- Cause: Synchronous loop without parallelization
- Improvement path: Use concurrent.futures ThreadPoolExecutor to download multiple files simultaneously

**API Calls Not Cached:**
- Problem: Every command re-fetches case details even if recently accessed
- Files: `src/mc/cli/commands/case.py`
- Cause: No caching layer between CLI and API client
- Improvement path: Implement simple file-based cache with TTL for case metadata

**Token Refresh on Every Run:**
- Problem: Fresh access token requested on every command invocation
- Files: `src/mc/utils/auth.py:7-31`
- Cause: No token persistence or expiration tracking
- Improvement path: Cache access token with expiration time; only refresh when expired

## Fragile Areas

**Workspace Path Construction:**
- Files: `src/mc/controller/workspace.py:35`
- Why fragile: Path built from formatted account name and case summary; special characters in customer names could break filesystem
- Safe modification: Always test with edge cases (special chars, unicode, very long names); formatter in `src/mc/utils/formatters.py:6-40` attempts sanitization but may miss edge cases
- Test coverage: No unit tests for edge cases in path construction

**LDAP Search Parsing:**
- Files: `src/mc/integrations/ldap.py:61-102`
- Why fragile: Parses LDAP output using string splitting and regex; breaks if LDAP schema changes or returns unexpected format
- Safe modification: Test against various LDAP response formats; add error handling for missing fields
- Test coverage: No tests for malformed LDAP responses

**File Existence Checks:**
- Files: `src/mc/controller/workspace.py:52-88`
- Why fragile: Uses os.path.exists which can have race conditions; file type mismatch (file vs directory) returns FATAL but doesn't explain what's wrong
- Safe modification: Add better error messages explaining what was expected vs found; use pathlib for safer path operations
- Test coverage: No tests for race conditions or permission errors

**HTTP Error Handling:**
- Files: `src/mc/integrations/redhat_api.py`
- Why fragile: All API methods use `raise_for_status()` which raises generic HTTPError; no retry logic for transient failures
- Safe modification: Wrap API calls in try/except blocks; provide meaningful error messages for common HTTP status codes (401, 403, 404, 500)
- Test coverage: No tests for API error scenarios

## Scaling Limits

**Single-Threaded Architecture:**
- Current capacity: One operation at a time
- Limit: Processing 100 case attachments sequentially could take minutes
- Scaling path: Add async/await support or multiprocessing for bulk operations

**Local Filesystem Dependency:**
- Current capacity: Limited by local disk space and filesystem performance
- Limit: Thousands of cases with large attachment sets
- Scaling path: Add support for remote storage backends (S3, NFS) in future architecture

## Dependencies at Risk

**Python 3.8 Minimum:**
- Risk: Python 3.8 reaches end-of-life October 2024 (already passed)
- Impact: Security vulnerabilities won't be patched
- Migration plan: Update to Python 3.10+ minimum; test with newer Python versions

**Requests Library Only Dependency:**
- Risk: Single external dependency is good, but requests doesn't support async natively
- Impact: Limits concurrent operations
- Migration plan: Consider httpx as drop-in replacement with async support for future

**Missing Type Hints:**
- Risk: No type annotations throughout codebase despite mypy in dev dependencies
- Impact: mypy won't catch type errors; IDE autocomplete limited
- Migration plan: Gradually add type hints starting with public APIs; configure mypy strictness

## Missing Critical Features

**No Error Recovery:**
- Problem: If attachment download fails mid-process, no retry or resume capability
- Blocks: Downloading large case attachment sets over unreliable connections
- Priority: Medium

**No Logging Infrastructure:**
- Problem: All output via print() statements; no debug logging or audit trail
- Blocks: Troubleshooting production issues; understanding what operations were performed
- Priority: High

**No Configuration File Support:**
- Problem: Despite config-examples/ directory, no code reads YAML configs
- Blocks: All planned future features (profiles, mounts, container orchestration)
- Priority: High - blocking future development

**Container Features Not Implemented:**
- Problem: Container orchestration mentioned in README but not implemented
- Blocks: Core use case of per-case container isolation
- Priority: High - appears to be main project goal

## Test Coverage Gaps

**No Unit Tests:**
- What's not tested: All Python modules lack pytest unit tests
- Files: Entire `src/mc/` directory
- Risk: Refactoring could break functionality unnoticed
- Priority: High

**Shell Tests Only:**
- What's not tested: Only integration-level shell scripts in `tests/` directory
- Files: `tests/test_*.sh`
- Risk: Shell tests exist but only test happy paths; no error case testing
- Priority: Medium

**No Mock Testing:**
- What's not tested: API calls always hit real Red Hat APIs during testing
- Files: `src/mc/integrations/redhat_api.py`, `src/mc/integrations/ldap.py`
- Risk: Tests require valid credentials and network access; can't test error conditions
- Priority: High

**Edge Cases Uncovered:**
- What's not tested: Unicode in case summaries, very long account names, filesystem permission errors, network timeouts
- Files: `src/mc/controller/workspace.py`, `src/mc/utils/formatters.py`
- Risk: Production failures in edge cases
- Priority: Medium

**Empty Test Directories:**
- What's not tested: `tests/unit/`, `tests/integration/`, `tests/fixtures/` exist but contain only `__init__.py`
- Files: `tests/unit/`, `tests/integration/`, `tests/fixtures/`
- Risk: Structure suggests intent to add tests but none written
- Priority: High

---

*Concerns audit: 2026-01-20*
