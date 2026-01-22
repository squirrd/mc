---
phase: 04-security-hardening
verified: 2026-01-22T16:52:30Z
status: passed
score: 5/5 must-haves verified
---

# Phase 04: Security Hardening Verification Report

**Phase Goal:** Tool follows security best practices for production use
**Verified:** 2026-01-22T16:52:30Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Access tokens are validated for expiration and cached appropriately | ✓ VERIFIED | `TOKEN_CACHE_PATH = ~/.mc/token`, `is_token_expired()` with 5-min buffer, `load_token_cache()` and `save_token_cache()` present, file created with 0600 permissions |
| 2 | All HTTP requests explicitly verify SSL certificates | ✓ VERIFIED | ALL 6 requests calls have `verify=` parameter (auth.py:129, redhat_api.py:100,125,150,175,196), `get_ca_bundle()` checks REQUESTS_CA_BUNDLE/CURL_CA_BUNDLE env vars, SSL errors show helpful messages |
| 3 | Case number input is validated (8 digits) before making API calls | ✓ VERIFIED | `validate_case_number()` function exists with regex `r'^\d{8}$'`, imported in case.py:5, used in all 4 commands (attach:21, check:78, create:125, case_comments:182) |
| 4 | Large file downloads (>3GB) show warning but don't block workflow | ✓ VERIFIED | `check_download_safety()` function with 3GB threshold, warning shows file size/free space/estimated time, RuntimeError only on insufficient space, CLI catches RuntimeError and continues (case.py:60-63) |
| 5 | Security linting (bandit) passes with no critical issues | ✓ VERIFIED | Bandit 1.9.3 installed in pyproject.toml, .bandit config exists with HIGH severity threshold, scan shows 0 HIGH/0 MEDIUM issues (only 6 LOW informational), LDAP subprocess calls have 4 nosec annotations with justifications |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mc/utils/auth.py` | Token caching with expiration validation | ✓ VERIFIED | 146 lines, contains TOKEN_CACHE_PATH, EXPIRY_BUFFER_SECONDS=300, DEFAULT_TTL_SECONDS=3600, is_token_expired(), load_token_cache(), save_token_cache(), get_ca_bundle(), updated get_access_token() with cache logic |
| `src/mc/utils/validation.py` | Input validation functions | ✓ VERIFIED | 30 lines, exports validate_case_number(), regex validation `r'^\d{8}$'`, clear ValueError messages with examples |
| `src/mc/integrations/redhat_api.py` | SSL verification and large file safety checks | ✓ VERIFIED | 207 lines, contains get_ca_bundle(), check_download_safety(), verify_ssl instance variable, all 6 requests have verify=self.verify_ssl and timeout=30, HEAD request before download |
| `src/mc/utils/auth.py` | SSL verification for token endpoint | ✓ VERIFIED | Same file, auth.py:129 has verify=ca_bundle and timeout=30 on SSO POST request |
| `src/mc/cli/commands/case.py` | Validation at command entry points | ✓ VERIFIED | 196 lines, imports validate_case_number on line 5, try/except ValueError in all 4 commands (attach, check, create, case_comments), RuntimeError handling for download failures |
| `tests/unit/test_validation.py` | Validation test suite | ✓ VERIFIED | 78 lines, 9 comprehensive tests covering valid/invalid/edge cases, all tests pass |
| `tests/unit/test_redhat_api.py` | Download safety tests | ✓ VERIFIED | 223 lines, 3 download safety tests (small file, large+space, insufficient space), all tests pass, mocks shutil.disk_usage correctly |
| `pyproject.toml` | Bandit dependency in dev dependencies | ✓ VERIFIED | Line 35: "bandit>=1.7.0", also [tool.bandit] section lines 91-93 |
| `.bandit` | Bandit configuration for project | ✓ VERIFIED | 20 lines, YAML config with exclude_dirs, severity: HIGH, confidence: MEDIUM |
| `~/.mc/token` | Cached token with expiration timestamp | ⚠️ WILL BE CREATED | File doesn't exist yet (no auth has been run), but auth.py:89 creates with 0600 permissions via os.open(), save_token_cache() includes expires_at field, permissions verified at line 94-97 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/mc/utils/auth.py` | `~/.mc/token` | JSON file I/O | ✓ WIRED | load_token_cache() opens TOKEN_CACHE_PATH with json.load() (line 58), save_token_cache() writes with json.dump() (line 91), atomic write with os.open(O_CREAT\|O_WRONLY\|O_TRUNC, 0o600) |
| `src/mc/cli/commands/case.py` | `src/mc/utils/validation.py` | validate_case_number import | ✓ WIRED | Import on line 5, called in 4 places (lines 21, 78, 125, 182), try/except catches ValueError and prints error |
| `src/mc/integrations/redhat_api.py` | requests library | verify parameter in all requests calls | ✓ WIRED | ALL 6 requests (POST/GET/HEAD) have verify=ca_bundle or verify=self.verify_ssl, grep confirms 0 unverified requests |
| `src/mc/integrations/redhat_api.py` | shutil.disk_usage | disk space check before download | ✓ WIRED | check_download_safety() calls shutil.disk_usage(os.path.dirname(download_path)) on line 41, used in download_file() on line 186 |
| `src/mc/cli/commands/case.py` | RuntimeError handling | download failures | ✓ WIRED | try/except RuntimeError in attach() function lines 58-63, prints error and continues to next attachment |
| `.bandit` | `src/mc/integrations/ldap.py` | nosec annotation on subprocess calls | ✓ WIRED | 4 nosec annotations found (B602, B603 twice, B607), each has detailed justification explaining why LDAP subprocess is safe |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| SEC-01: Access token expiration validation and caching | ✓ SATISFIED | All truths verified - token cache at ~/.mc/token with 5-min buffer, expires_in from SSO, 1-hour default TTL |
| SEC-02: Explicitly set verify=True in all requests calls | ✓ SATISFIED | All 6 HTTP requests have verify parameter with CA bundle support via environment variables |
| SEC-03: Case number format validation (8 digits) | ✓ SATISFIED | validate_case_number() regex validation at command entry points, fail-fast before API calls |
| SEC-04: File size warning for downloads >3GB (no prompting) | ✓ SATISFIED | check_download_safety() with 3GB threshold, shows warning with disk space info, blocks only on insufficient space (no user prompt) |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| N/A | - | - | - | No blocker anti-patterns found |

**Note:** Bandit scan identified 6 LOW severity informational issues (B404 subprocess import, B607/B603 subprocess usage in LDAP, B105 empty string false positives). All are documented with nosec annotations or are known safe. Zero HIGH/MEDIUM severity issues.

### Human Verification Required

#### 1. Token Cache Persistence Across Sessions

**Test:** 
1. Run `mc check 12345678 ~/Cases` (first time - will fetch token from SSO)
2. Check `ls -la ~/.mc/token` shows file with 600 permissions
3. Run `mc check 12345678 ~/Cases` again immediately
4. Second invocation should be faster (uses cache instead of SSO call)

**Expected:** 
- Token cache file created with `-rw-------` permissions
- Second invocation reuses cached token (no SSO HTTP call)
- Cache contains JSON with `access_token`, `expires_at`, `token_type` fields

**Why human:** Need actual Red Hat credentials and network access to test SSO integration. File existence/permissions can be automated but token reuse requires timing comparison.

#### 2. Case Number Validation User Experience

**Test:**
1. Run `mc attach 123 ~/Cases` (too short)
2. Run `mc attach 123456789 ~/Cases` (too long)
3. Run `mc attach abcd1234 ~/Cases` (non-numeric)
4. Run `mc attach 12345678 ~/Cases` (valid)

**Expected:**
- Invalid cases 1-3: Show "Error: Invalid case number: 'X'. Case number must be exactly 8 digits. Example: 12345678" and exit without making API calls
- Valid case 4: Validation passes, proceeds to API call (may fail if case doesn't exist, but validation succeeded)

**Why human:** Error message clarity and user experience assessment requires human judgment. Automated tests verify function logic but not message helpfulness.

#### 3. Large File Download Warning Display

**Test:**
1. Trigger download of file >3GB (need real case with large attachment)
2. Observe warning message format
3. Verify estimated download time is reasonable
4. Confirm download proceeds (if space available) or blocks (if insufficient space)

**Expected:**
- Warning shows: File name, size in GB, free disk space in GB, estimated download time
- If free space > (file size * 1.1): warning displays but download continues
- If free space < (file size * 1.1): error shows "Insufficient disk space" and download blocked

**Why human:** Need real large file to test, estimated download time calculation accuracy needs human assessment, visual clarity of warning message.

#### 4. SSL Certificate Verification with Custom CA Bundle

**Test:**
1. Run `mc check 12345678 ~/Cases` normally (should work)
2. Run `REQUESTS_CA_BUNDLE=/invalid/path mc check 12345678 ~/Cases`
3. Observe error message

**Expected:**
- Normal run: SSL verification succeeds with certifi default bundle
- Invalid CA path: Shows "SSL certificate verification failed for https://..." with helpful remediation message about REQUESTS_CA_BUNDLE environment variable

**Why human:** SSL error messages need to be helpful and not scary. Human assessment of message clarity and actionability required.

#### 5. Security Scan Integration into Workflow

**Test:**
1. Run `bandit -c .bandit -r src/` manually
2. Open `.planning/phases/04-security-hardening/bandit-report.html` in browser
3. Review findings categorization (HIGH/MEDIUM/LOW)
4. Check nosec justifications make sense

**Expected:**
- Command completes with exit code 0
- HTML report shows zero HIGH/MEDIUM severity issues
- LOW severity issues have clear nosec annotations explaining why safe
- Report is readable and provides actionable information

**Why human:** Security report interpretation requires security expertise. Automated checks verify no HIGH/MEDIUM issues, but human needs to assess if LOW issues are truly safe.

### Gaps Summary

**No gaps found.** All must-haves verified at all three levels:

1. **Existence:** All required files and functions present
2. **Substantive:** All implementations meet minimum line counts and contain required logic (no stubs)
3. **Wired:** All connections verified (imports used, functions called, parameters passed)

**Phase goal achieved:** Tool follows security best practices for production use.

- ✅ Token caching reduces SSO calls and validates expiration
- ✅ SSL verification prevents MITM attacks with CA bundle support
- ✅ Input validation prevents invalid API calls (fail-fast)
- ✅ Large file safety prevents disk space issues
- ✅ Security linting catches vulnerabilities before merge
- ✅ HTTP timeouts prevent DoS from slow servers

---

_Verified: 2026-01-22T16:52:30Z_
_Verifier: Claude (gsd-verifier)_
