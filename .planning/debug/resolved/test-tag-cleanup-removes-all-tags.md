---
status: resolved
trigger: "Investigate issue: test-tag-cleanup-removes-all-tags"
created: 2026-02-10T00:00:00Z
updated: 2026-02-10T00:06:30Z
---

## Current Focus

hypothesis: CONFIRMED - skopeo delete deletes by manifest digest, removing ALL tags. Solution is to not delete the test tag.
test: Verify that leaving test-digest tag in registry causes no harm
expecting: The test tag is temporary and can be safely left in registry or overwritten on next run
next_action: Implement fix by removing the skopeo delete commands

## Symptoms

expected: Only the test_registry_tag should be deleted, but all other tags (like 'latest') should remain pointing to the same image in the registry (quay.io)
actual: When the cleanup runs (line 681: `skopeo delete "docker://${REGISTRY_REPO}:${test_registry_tag}"`), the 'latest' tag and other tags disappear along with the test tag, making the image invisible in quay.io
errors: No error messages - the script runs without errors, but the behavior is wrong
reproduction: Run the build script (container/build-container.sh) twice. The second build detects the unchanged image and triggers the test tag cleanup section ("Image unchanged (manifest match), cleaning up test tag..."), which causes all tags to disappear
started: User noticed this after the recent container build changes. The issue occurs when the "Image unchanged (manifest match), cleaning up test tag..." section runs.

## Eliminated

## Evidence

- timestamp: 2026-02-10T00:01:00Z
  checked: container/build-container.sh lines 681 and 700
  found: Using `skopeo delete "docker://${REGISTRY_REPO}:${test_registry_tag}"` to delete test tag
  implication: When passing a tag (not digest), skopeo resolves it to manifest digest

- timestamp: 2026-02-10T00:02:00Z
  checked: skopeo delete documentation and behavior
  found: "When using a tag (rather than a digest), skopeo currently resolves the tag into a digest and then deletes the manifest by digest, possibly deleting all tags pointing to that manifest, not just the provided tag"
  implication: This is documented skopeo behavior - it deletes the underlying manifest, affecting ALL tags pointing to same digest

- timestamp: 2026-02-10T00:03:00Z
  checked: Alternative tools for tag-only deletion
  found: regctl provides tag deletion API that only deletes a single tag even if multiple tags point to same digest
  implication: Need to either use regctl or stop trying to delete the test tag altogether

- timestamp: 2026-02-10T00:04:00Z
  checked: System availability of regctl
  found: regctl is not installed on the system
  implication: Cannot use regctl without adding new dependency

- timestamp: 2026-02-10T00:05:00Z
  checked: Best practices for temporary test tags
  found: Registry cleanup policies and retention policies are standard approaches. Leaving a test tag is harmless - it will be overwritten on next build and registries can be configured with cleanup policies for unused tags
  implication: Safest solution is to remove the skopeo delete commands and leave the test tag in registry

## Resolution

root_cause: skopeo delete resolves tags to manifest digests before deletion. When deleting "test-digest" tag, it resolves to the same manifest digest as "latest" and other tags, then deletes that manifest, causing ALL tags pointing to it (including "latest") to be removed from the registry.

fix: Removed both skopeo delete commands (lines 681-682 and 700-701). The test-digest tag is now left in the registry where it will be harmlessly overwritten on the next build. Added explanatory comments documenting why we don't delete the tag.

verification: PASSED
  - Bash syntax check: passed (no errors)
  - Code review: Both skopeo delete commands removed successfully
  - Logic verified: Script now skips deletion entirely, leaving test tag in registry
  - Comments added: Clear explanation of why deletion was removed
  - Expected behavior: test-digest tag will remain in registry and be overwritten on next build, other tags (like 'latest') will no longer be accidentally deleted

files_changed:
  - container/build-container.sh
