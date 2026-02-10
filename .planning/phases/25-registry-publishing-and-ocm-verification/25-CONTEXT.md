# Phase 25: Registry Publishing & OCM Verification - Context

**Gathered:** 2026-02-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Publish versioned container images to quay.io registry and validate OCM CLI tool integration end-to-end. This phase implements the registry push workflow (building on Phase 24's auto-versioning) and verifies OCM tool installation. Future OCM configuration and operational testing belongs in separate phases.

</domain>

<decisions>
## Implementation Decisions

### Publishing Workflow
- **Auto-push behavior:** Inherited from Phase 24 - digest-based auto-push (when digest differs, automatically bump and push)
- **Tag strategy:** Only two tags per push: semantic version (e.g., 1.2.18) and :latest
- **Push output:** Detailed push summary showing registry URL, tags pushed, image size, and digest
- **Atomic push requirement:** Both version tag AND :latest tag must succeed, or build fails
- **Pre-flight validation:** Verify registry credentials before building to avoid wasted build time
- **Push failure handling:** Leave local tags intact on push failure (user can retry manually)
- **Network failure:** Fail immediately if quay.io unavailable (no offline mode, registry required for versioning)

### OCM Verification Depth
- **Verification scope:** Version match only - `ocm version` output must match versions.yaml
- **Integration test:** Non-mocked integration test comparing OCM version in container to versions.yaml
- **Test timing:** Claude's discretion (during build or post-build)
- **Architecture coverage:** Current architecture only (test on platform where test runs)
- **Version mismatch:** Fail test hard - version mismatch is critical error with non-zero exit
- **Rationale:** Deeper OCM configuration/functional testing deferred to future milestone

### Error Handling & Rollback
- **Failed push:** Leave local tags, fail build (no automatic cleanup or retry)
- **Invalid credentials:** Pre-flight credential check before building
- **OCM download failure:** Fail build immediately (no retry)
- **SHA256 mismatch:** Fail build immediately (no retry)
- **Registry unavailable:** Fail immediately (no local-only build mode)

### Security & Authentication
- **Token storage:** Separate config file (e.g., `.registry-auth`) in MC base directory, gitignored
- **Auth mechanism:** Token-based (not password) for registry authentication
- **SHA256 verification:** Mandatory - build fails on checksum mismatch, no override
- **Registry configuration:** Fixed location in config file under MC base directory (mc-cli will sync with same location)
- **User modification:** Users cannot modify registry URL/repository (hardcoded in config)
- **Logging:** Full transparency - log registry URL, image digest, tags (no secrets in logs)

### Claude's Discretion
- Exact file path and name for registry auth config in MC base directory
- Config file format (JSON, YAML, etc.)
- Token fallback: whether to support QUAY_TOKEN env var as alternative to config file
- Exact credential validation mechanism
- Error message formatting and verbosity for auth failures

</decisions>

<specifics>
## Specific Ideas

- Registry auth config lives in MC base directory (not container/ directory) so mc-cli can share the same registry configuration
- Pre-flight credential check prevents wasted build time on auth failures
- Full transparency logging helps debug push issues without exposing secrets
- Version-only OCM verification keeps this phase focused - functional testing comes later

</specifics>

<deferred>
## Deferred Ideas

- OCM configuration and functional testing - future milestone
- Multi-architecture testing (amd64/arm64) - current arch only for now
- Retry logic for push failures - fail fast for now
- Alternative registry support - quay.io only for now

</deferred>

---

*Phase: 25-registry-publishing-and-ocm-verification*
*Context gathered: 2026-02-10*
