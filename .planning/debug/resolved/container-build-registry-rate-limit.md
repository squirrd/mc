---
status: fixing
trigger: "container-build-registry-rate-limit: Container build script failing with 'too many requests to registry' error when attempting first push of version 1.0.0 to quay.io/dsquirre/mc-rhel10"
created: 2026-02-10T00:00:00Z
updated: 2026-02-10T01:30:00Z
---

## Current Focus

hypothesis: CONFIRMED - Rate limit is triggered by COMBINATION of 3+ pre-push registry queries (find_latest_patch, get_registry_digest, check_version_exists) happening in close succession with subsequent podman push blob checks.
test: Applied fix - reverted to podman push with 10 second sleep delay before push operations
expecting: 10 second delay allows quay.io rate limit window to reset between query and push phases, preventing combined operations from exceeding "few requests per second" threshold
next_action: User verification - run ./container/build-container.sh and confirm successful push without HTTP 429 errors

## Symptoms

expected: Should successfully push the container image to quay.io with tag 1.0.0 (first build for 1.0.* series, so starting at patch level 0)

actual: Build completes successfully (image 859dd783581...), but push fails partway through copying blobs with error: "Error: trying to reuse blob sha256:1e5305e1405b7a62bf480edc505925402a83f205994173a7eb0f911479d1dbc2 at destination: too many requests to registry"

errors:
```
Error: trying to reuse blob sha256:1e5305e1405b7a62bf480edc505925402a83f205994173a7eb0f911479d1dbc2 at destination: too many requests to registry
```

Full output shows:
- Registry credentials validated successfully
- Query for latest 1.0.* version succeeded (no tags found)
- Build succeeded (image ID: 859dd78358113134ea1243d1729acc43cf1ce8bdd2807ce227cf173436d50588)
- Push started, began copying 9 blobs
- Failed on the 2nd blob during "reuse" operation

reproduction: Run `./container/build-container.sh` from repo root

started: First time running this build script. No prior push attempts. User reports no recent pushes to this or other registries in the last few minutes.

## Eliminated

- hypothesis: Missing --retry flag causes immediate failure on HTTP 429
  evidence: Added --retry 5 --retry-delay 2s to both podman push commands (lines 617-618), but error still occurs with identical message. No retry attempts visible in output. Same blob causing error (sha256:1e5305e1405b...). User verified fix was applied and ran build again.
  timestamp: 2026-02-10T00:15:00Z

- hypothesis: Two sequential pushes (version tag + latest tag) cause rate limit by making 18+ rapid API calls
  evidence: User confirmed error STILL occurs after adding sleep 3 between push commands. Critical observation: "I dont think there was a 3 second delay between copying the blobs" - this means error happens DURING FIRST PUSH before script reaches sleep command. Error output shows blob copying starts and fails within a single push operation.
  timestamp: 2026-02-10T00:30:00Z

- hypothesis: Using skopeo copy with --image-parallel-copies 1 will serialize blob operations and prevent rate limit
  evidence: Skopeo syntax error - containers-storage reference "mc-rhel10:1.0.0" doesn't resolve. Needs "localhost/" prefix. More importantly, user correctly identified simpler solution: podman push IS designed for this use case, just need delay BEFORE push to separate pre-push queries from push operations.
  timestamp: 2026-02-10T01:30:00Z

## Evidence

- timestamp: 2026-02-10T00:01:00Z
  checked: build-container.sh push commands (lines 617-618)
  found: Two sequential podman push operations with --authfile flag, no retry logic or rate limit handling
  implication: Script does not handle transient rate limit errors

- timestamp: 2026-02-10T00:02:00Z
  checked: Containerfile base images
  found: Uses registry.access.redhat.com/ubi10/ubi-minimal:latest and registry.access.redhat.com/ubi10/ubi:10.1 as base images
  implication: These are public Red Hat UBI images that likely have shared layers across many container images in registries

- timestamp: 2026-02-10T00:03:00Z
  checked: Error message details
  found: Error occurs during "reuse blob" operation on 2nd of 9 blobs, specifically during push to destination registry
  implication: Podman is attempting to check if blobs already exist on quay.io (blob mounting optimization) which requires API calls that count against rate limits

- timestamp: 2026-02-10T00:04:00Z
  checked: podman push --help for retry options
  found: --retry uint flag exists (number of times to retry in case of failure) and --retry-delay string flag for delay between retries
  implication: Podman has built-in retry mechanism but build script is not using it

- timestamp: 2026-02-10T00:05:00Z
  checked: Quay.io rate limiting policies (Red Hat documentation)
  found: Quay.io rate limits API requests to "a few requests per second per IP" with bursting capabilities. Limits apply to all API endpoints including blob mount operations. Returns HTTP 429 when exceeded. Unlike Docker Hub, quay.io only rate limits in severe circumstances (tens of requests per second)
  implication: First-time push with 9 blobs triggers multiple blob mount checks in rapid succession, potentially hitting the "few requests per second" threshold

- timestamp: 2026-02-10T00:06:00Z
  checked: Red Hat Customer Portal solution for "Failed to pull or push reuse blob"
  found: Common issue with blob reuse operations triggering rate limits or timeouts when podman attempts to check if blobs exist before pushing
  implication: This is a known issue pattern with container registry operations

- timestamp: 2026-02-10T00:15:00Z
  checked: User verification after retry fix applied
  found: Error still occurs with identical message after adding --retry 5 --retry-delay 2s. Different image hash (86ef98dab472...) but same blob causing error (sha256:1e5305e1405b...). No retry attempts visible in output.
  implication: Retry flags are either not working for blob reuse operations, or not being applied correctly, or blob reuse errors are not retryable by podman

- timestamp: 2026-02-10T00:16:00Z
  checked: Podman documentation and GitHub issues about --retry behavior
  found: Podman retry mechanism respects Retry-After header from registries (60s for HTTP 429). Default retry is 3 times with exponential backoff starting at 2 seconds. --retry flag exists but behavior with blob mount operations unclear.
  implication: Registry may be returning Retry-After header requiring longer delays than our 2s setting, or blob mount checks bypass retry logic entirely

- timestamp: 2026-02-10T00:17:00Z
  checked: podman push --help output
  found: Flags available: --retry uint (number of times to retry in case of failure), --retry-delay string (delay between retries). No flags for disabling blob mount/reuse optimization.
  implication: No built-in way to disable blob mount optimization via podman push flags

- timestamp: 2026-02-10T00:18:00Z
  checked: build-container.sh push logic (lines 617-618)
  found: Script does TWO sequential podman push commands with NO delay between them: (1) version tag, (2) latest tag. Both push the exact same image (same blobs).
  implication: First push succeeds or partially succeeds, then second push immediately tries to check/mount the same blobs, triggering rate limit. The two rapid pushes of identical content are the cause of exceeding "few requests per second" threshold.

- timestamp: 2026-02-10T00:30:00Z
  checked: User feedback after sleep 3 fix applied
  found: Error still occurs. User reports "I dont think there was a 3 second delay between copying the blobs" - meaning the blob copying output happens rapidly within the FIRST push, before the sleep command is reached.
  implication: PREVIOUS DIAGNOSIS WAS WRONG. The rate limit is NOT about two sequential pushes - it's about rapid blob mount checks WITHIN a single podman push operation (9 blobs checked in rapid succession).

- timestamp: 2026-02-10T00:31:00Z
  checked: Error message sequence from user output
  found: Error occurs during "Copying blob" phase of a SINGLE push operation. All blob copying lines appear together, then error. No evidence of second push command being reached.
  implication: Within one podman push command, podman rapidly makes API calls to check if each of 9 blobs already exists on quay.io (blob mount optimization). These 9+ rapid API calls in <1 second exceed quay.io's "few requests per second" threshold.

- timestamp: 2026-02-10T00:35:00Z
  checked: Quay.io rate limiting documentation (Red Hat Customer Portal)
  found: Quay.io limits requests to "a few requests per second per IP" with bursting capabilities. Returns HTTP 429 when exceeded. Rate limit is global across all API endpoints including blob mount operations.
  implication: The 9 blob mount checks in rapid succession are hitting this threshold during the FIRST push operation.

- timestamp: 2026-02-10T00:36:00Z
  checked: Podman push --help for blob mount control options
  found: No flags available to disable or slow down blob mount/reuse optimization. Available flags: --retry, --retry-delay, --compression-format, --force-compression, --tls-verify, etc. Nothing for blob mount behavior control.
  implication: Cannot control blob mount rate directly via podman push flags.

- timestamp: 2026-02-10T00:37:00Z
  checked: Cross-repository blob mounting research (GitHub issues)
  found: "Cross Repository Blob Mount makes push too slow" (distribution/distribution #2988) - blob mount optimization can actually slow down pushes. Podman issue #17892 shows "push uploads already existing layers" - suggests blob mount detection doesn't always work correctly.
  implication: Blob mount optimization is built into the OCI distribution spec and happens automatically. It can cause both performance issues and rate limit issues.

- timestamp: 2026-02-10T00:38:00Z
  checked: Skopeo vs podman push behavior research
  found: Issue #17892 reports "Podman (and Buildah) are unable to detect the existence of the large base layers in the registry, and perform a re-upload again in every CI step. Skopeo however does not have this bug."
  implication: Skopeo may have different blob handling behavior than podman push, potentially making different rate limit trade-offs.

- timestamp: 2026-02-10T00:40:00Z
  checked: skopeo copy --help for parallelization control
  found: Flag available: --image-parallel-copies uint - "Maximum number of image layers to be copied (pulled/pushed) simultaneously. Not setting this field will fall back to containers/image defaults."
  implication: This flag controls how many layers are uploaded in parallel. Setting to 1 would serialize blob operations, potentially spreading API requests over more time and avoiding rate limit bursts.

- timestamp: 2026-02-10T01:00:00Z
  checked: Skopeo copy syntax error after initial fix
  found: Error "reference '[vfs@/Users/dsquirre/.local/share/containers/storage+/private/var/folders/4g/f4mcz0c54dxgchllwksqtfb40000gn/T/storage-run-501/containers]docker.io/library/mc-rhel10:1.0.0' does not resolve to an image ID". Command used: `skopeo copy containers-storage:${version_tag} docker://...` where $version_tag="mc-rhel10:1.0.0"
  implication: The variable $version_tag contains a docker-style reference (mc-rhel10:1.0.0), not a containers-storage reference. Skopeo needs proper storage path format.

- timestamp: 2026-02-10T01:05:00Z
  checked: build-container.sh pre-push registry queries (lines 468-485)
  found: Script calls find_latest_patch() which internally calls `skopeo list-tags "docker://${REGISTRY_REPO}"` to query ALL tags from registry, then filters with grep for matching minor version. This happens BEFORE any build or push.
  implication: Pre-push query fetches entire tag list from quay.io. If repository has many tags, this is one API call but potentially large response. Combined with subsequent push operations, this contributes to rate limit budget consumption.

- timestamp: 2026-02-10T01:10:00Z
  checked: Skopeo documentation for containers-storage format
  found: containers-storage reference format should be bare image name/ID that podman knows about, not full docker reference. Since image was tagged with `podman tag "$temp_tag" "$version_tag"` where version_tag="mc-rhel10:1.0.0", skopeo should reference it the same way.
  implication: Skopeo command should use just the tagged name as-is: `containers-storage:mc-rhel10:1.0.0` not `containers-storage:${version_tag}` (which is redundant since version_tag already contains "mc-rhel10:1.0.0")

- timestamp: 2026-02-10T01:15:00Z
  checked: Actual podman image repository names
  found: Running `podman images` shows all local images are stored with "localhost/" prefix: localhost/mc-rhel10:temp, localhost/mc-rhel10:1.0.0, localhost/mc-rhel10:latest
  implication: The containers-storage reference must include the "localhost/" prefix. Correct format: `containers-storage:localhost/mc-rhel10:1.0.0`

- timestamp: 2026-02-10T01:30:00Z
  checked: Full pre-push API call sequence in build script
  found: Script makes MULTIPLE registry API calls in sequence before push: (1) find_latest_patch() at line 473 calls skopeo list-tags, (2) get_registry_digest() at line 562 calls skopeo inspect, (3) check_version_exists() at line 597 calls skopeo inspect. Then immediately at line 617+ does podman push with blob mount checks.
  implication: The rate limit is triggered by the COMBINATION of 3+ pre-push API queries happening in close succession with subsequent push blob checks. All these calls happen within seconds, exceeding quay.io's "few requests per second" threshold.

## Resolution

root_cause: The build script makes multiple rapid API calls to quay.io in close succession: (1) find_latest_patch() calls skopeo list-tags, (2) get_registry_digest() calls skopeo inspect, (3) check_version_exists() calls skopeo inspect, then (4) podman push makes blob mount checks for 9 layers. All these calls happen within seconds, exceeding quay.io's "few requests per second per IP" rate limit threshold.

The issue is the COMBINATION of pre-push registry queries followed immediately by push blob mount checks, without any time gap for the rate limit window to reset.

fix: Added 10 second sleep delay BEFORE push operations. This separates the pre-push API query phase from the push blob check phase, allowing quay.io's rate limit window to reset between the two phases.

Also reverted from skopeo copy (which had syntax errors) back to podman push (which is designed for this use case), and retained --retry flags as defense-in-depth for transient errors.

Changed from:
  skopeo copy --image-parallel-copies 1 --retry-times 5 --authfile=... "containers-storage:localhost/${version_tag}" "docker://..."

Back to:
  sleep 10  # Allow rate limit window to reset after pre-push queries
  podman push --retry 5 --retry-delay 2s --authfile=... "$version_tag" "docker://..."

Benefits:
- Separates pre-push API calls from push API calls with time gap
- Allows rate limit window to reset between phases
- Uses podman push which is designed for pushing to quay.io
- Retains retry logic for transient errors
- Simpler solution than switching tools

verification: Pending - user needs to run ./container/build-container.sh to verify both pushes complete successfully without HTTP 429 errors

files_changed:
  - container/build-container.sh (lines 617-637: reverted to podman push, added sleep 10 delay before push)
