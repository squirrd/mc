---
phase: 34-case-data-store
plan: 01
subsystem: api
tags: [redhat-api, requests, mypy, typeddict, unit-tests, responses]

# Dependency graph
requires:
  - phase: 33-container-mounts
    provides: container workspace foundation that the case data will be written into
provides:
  - fetch_case_comments() method on RedHatAPIClient for GET /support/v1/cases/{case_number}/comments
  - openshiftClusterID and customerName fields added to CaseDetails TypedDict
  - Unit tests for fetch_case_comments() covering happy path and all error cases
affects:
  - 34-02 and subsequent plans that write sfdc-case.json and sfdc-comments.json
  - 35-backplane-auto-login which needs openshiftClusterID as cluster ID source

# Tech tracking
tech-stack:
  added: []
  patterns:
    - fetch_case_comments() follows same error handling pattern as fetch_case_details() and list_attachments()
    - responses.add_callback() used for timeout and connection error simulation in tests

key-files:
  created: []
  modified:
    - src/mc/integrations/redhat_api.py
    - tests/unit/test_redhat_api.py

key-decisions:
  - "fetch_case_comments() return type is list[dict[str, Any]] — no filtering or transformation of API response"
  - "openshiftClusterID added as NotRequired[str] to CaseDetails — it may not be present on all cases"
  - "customerName added as NotRequired[str] to CaseDetails — matches what the API returns"

patterns-established:
  - "New API methods follow: url build → session.get → raise_for_status → cast → return; same except chain for HTTP/Retry/Timeout/Connection/RequestException errors"

# Metrics
duration: 2min
completed: 2026-03-20
---

# Phase 34 Plan 01: Extend RedHatAPIClient with Comments Endpoint Summary

**fetch_case_comments() added to RedHatAPIClient with openshiftClusterID and customerName added to CaseDetails TypedDict, plus 5 unit tests covering happy path and all error cases**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-20T11:25:50Z
- **Completed:** 2026-03-20T11:27:03Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Extended `CaseDetails` TypedDict with `openshiftClusterID: NotRequired[str]` and `customerName: NotRequired[str]`
- Added `fetch_case_comments()` method to `RedHatAPIClient` with URL `/support/v1/cases/{case_number}/comments`
- 5 new unit tests covering: happy path list, empty list, 401 HTTP error, timeout, and connection error

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend CaseDetails TypedDict and add fetch_case_comments()** - `d6ba089` (feat)
2. **Task 2: Add unit tests for fetch_case_comments()** - `1626dce` (test)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `src/mc/integrations/redhat_api.py` - Added openshiftClusterID + customerName to CaseDetails, added fetch_case_comments() method
- `tests/unit/test_redhat_api.py` - Added APITimeoutError/APIConnectionError imports and 5 test functions

## Decisions Made

- Return type `list[dict[str, Any]]` — no filtering of API response, raw pass-through matching the same pattern as `list_attachments()`
- Both `openshiftClusterID` and `customerName` marked `NotRequired` — these fields may be absent in API responses for cases without OpenShift clusters

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `fetch_case_comments()` is ready for use in Phase 34 plans that write sfdc-comments.json inside the container
- `openshiftClusterID` is now accessible from `CaseDetails` for use in case.env generation (MC_CLUSTER_EXTERNAL_ID)
- All 24 tests in test_redhat_api.py pass; mypy clean

---
*Phase: 34-case-data-store*
*Completed: 2026-03-20*
