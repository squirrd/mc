---
status: resolved
trigger: "build-script-false-image-changes"
created: 2026-02-10T00:00:00Z
updated: 2026-02-10T00:12:00Z
---

## Current Focus

hypothesis: Fix implemented - now verifying it works correctly
test: Run build script and verify it detects identical image and skips bump/push
expecting: Script will report "Image unchanged (digest match), skipping bump and push" instead of pushing a new version
next_action: Test the fix by running build-container.sh

## Symptoms

expected: Script should detect when the built image is identical to what's in the registry and skip pushing. Only push when actual changes occur.

actual: Every build reports "Image changed (digest mismatch)" and pushes a new version (1.0.0, then 1.0.1, then 1.0.2), even though the image hash is identical (ec7660889873bf3e50f2ca7ed0c57bdf1603a40f1a929e5b9bdc7cde1929abea) across all builds. All blobs are the same (sha256:46be1bdca4b..., sha256:85a0f9efc08f..., etc.).

errors: No error messages, but incorrect behavior: "Image changed (digest mismatch), bumping version..." appears even when nothing changed.

reproduction:
1. Run ./container/build-container.sh (pushes 1.0.0)
2. Immediately run ./container/build-container.sh again without any code changes (pushes 1.0.1 - SHOULD SKIP)
3. Run a third time (pushes 1.0.2 - SHOULD SKIP)

All three builds produce identical image hash ec7660889873bf3e50f2ca7ed0c57bdf1603a40f1a929e5b9bdc7cde1929abea and identical blob hashes.

started: User just discovered this behavior after fixing registry authentication issues. Unknown if it ever worked correctly. The script is designed to do semantic versioning with digest comparison.

## Eliminated

- hypothesis: Using skopeo inspect docker-daemon for local image will provide comparable digest to registry
  evidence: Tested and found docker-daemon digest (sha256:3b22f25f...) still doesn't match registry digest after push (sha256:ef37e4426...). The push operation creates a new manifest with different digest.
  timestamp: 2026-02-10T00:07:00Z

## Evidence

- timestamp: 2026-02-10T00:01:00Z
  checked: build-container.sh digest comparison logic (lines 585-614)
  found: Line 587 gets local_digest using `podman inspect` on temp tag, extracts `.Digest` field. Line 601 gets registry_digest using `get_registry_digest()` function. Line 603 compares the two.
  implication: Need to verify what `.Digest` field returns from podman inspect vs what skopeo inspect returns

- timestamp: 2026-02-10T00:02:00Z
  checked: get_registry_digest() function (lines 378-386)
  found: Uses `skopeo inspect "docker://${REGISTRY_REPO}:${version}"` and extracts `.Digest` field via jq
  implication: Both local and registry use `.Digest` field, but from different tools (podman vs skopeo)

- timestamp: 2026-02-10T00:03:00Z
  checked: Research on podman vs skopeo digest behavior
  found: For multi-arch images, podman inspect and skopeo inspect return DIFFERENT digest values. Skopeo returns the manifest list digest (multi-arch), while podman may return the architecture-specific manifest digest. This is a known issue documented in containers/podman#15803 and containers/skopeo#1554.
  implication: The script compares two different types of digests, causing false positives even when images are identical

- timestamp: 2026-02-10T00:04:00Z
  checked: Actual digest values from local image and registry
  found: Local image (podman inspect mc-rhel10:temp): sha256:a916d8076f07707039eb7a0668652a5dc73c672c8980fbb7f29ba00c32a58309. Registry image (skopeo inspect 1.0.2): sha256:07245fcd3118a014bbca04ecbff53a222ec8f555dc8bf9cbfc277b4e028cc23e. These are DIFFERENT even though the image is identical (same IMAGE ID ec7660889873).
  implication: ROOT CAUSE CONFIRMED - Script compares apples to oranges (image config digest vs manifest digest)

- timestamp: 2026-02-10T00:05:00Z
  checked: All three registry versions (1.0.0, 1.0.1, 1.0.2)
  found: All three have IDENTICAL manifest digest sha256:07245fcd3118a014bbca04ecbff53a222ec8f555dc8bf9cbfc277b4e028cc23e
  implication: The images ARE identical on the registry, confirming the bug is in the comparison logic, not in actual image differences

- timestamp: 2026-02-10T00:07:00Z
  checked: First fix attempt using skopeo inspect docker-daemon
  found: Still doesn't work. docker-daemon digest (sha256:3b22f25f...) doesn't match what gets pushed to registry (sha256:ef37e4426...). The push operation itself creates a new manifest.
  implication: Cannot compare pre-push digest with registry. Must either compare post-push OR use a different strategy

- timestamp: 2026-02-10T00:08:00Z
  checked: Implemented layer digest comparison instead of manifest digest
  found: Still detects changes on every build! Layer digests are different (local: 020dc498c... vs registry: 0b755a3a...). Builds are NOT reproducible.
  implication: The builds themselves are non-deterministic, not just the digest comparison

- timestamp: 2026-02-10T00:09:00Z
  checked: Containerfile builds and Python bytecode
  found: Image contains Python .pyc files (in .venv/lib/python*/site-packages/__pycache__/). Python bytecode files include timestamps by default, making builds non-reproducible.
  implication: ROOT CAUSE IS DEEPER - builds are non-deterministic due to Python bytecode timestamps

- timestamp: 2026-02-10T00:10:00Z
  checked: Added SOURCE_DATE_EPOCH to make builds reproducible
  found: Registry manifests for 1.0.8 and 1.0.9 are IDENTICAL (sha256:772bc78194...), registry layers are IDENTICAL. Reproducible builds WORK!
  implication: BUT local docker-daemon layers differ from registry layers after push. Cannot compare pre-push local layers with registry.

- timestamp: 2026-02-10T00:11:00Z
  checked: Why local vs registry layers differ
  found: Podman push recompresses or processes layers during push operation. Local docker-daemon layers (sha256:260c4269fa...) become different registry layers (sha256:0b755a3adb...) even though content is identical.
  implication: Must compare REGISTRY digest post-push with PREVIOUS version's registry digest, not local with registry

## Resolution

root_cause: TWO ISSUES: (1) Script compares incompatible digest types - podman inspect returns image config digest while skopeo inspect returns manifest digest, and local docker-daemon layers differ from registry layers after push due to recompression. (2) Builds are NON-REPRODUCIBLE because Python pip install creates .pyc bytecode files with embedded timestamps, making every build produce different layers even with identical source code.

fix: (1) Made builds reproducible by adding SOURCE_DATE_EPOCH=1704067200 build arg in build-container.sh and passing it to pip install commands in Containerfile. This makes Python bytecode timestamps deterministic. (2) Changed comparison strategy: push to temporary "test-digest" tag, compare its registry manifest digest with previous version's registry manifest digest, delete test tag if identical (skip bump), or proceed with version bump if different. This ensures comparing same digest types (both registry manifests).

verification: Tested by running build script three times: first push (1.0.10 with fixes), second run immediately after showed "Image unchanged (manifest match), cleaning up test tag... Build completed in 34s (no-op)" - SUCCESS. Verified 1.0.8 and 1.0.9 have identical registry digests (sha256:772bc78194...) confirming reproducible builds work.

files_changed:
  - container/build-container.sh
  - container/Containerfile
