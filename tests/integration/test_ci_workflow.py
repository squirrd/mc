"""Acceptance tests for MC-86: CI container publish workflow.

Feature: Automate container image build and push to quay.io on version release
via GitHub Actions, eliminating manual build/push discipline and preventing
stale container images.

These tests validate that the GitHub Actions workflow files exist and contain
the expected structure for automated container publishing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml


# Resolve the repo root from the test file location
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOW_FILE = WORKFLOW_DIR / "release-container.yml"


@pytest.mark.integration
def test_mc_86_ci_container_publish_workflow_test_gate_acceptance() -> None:
    """Acceptance test for slice: workflow-test-gate.

    Feature  : MC-86-ci-container-publish
    Slice    : workflow-test-gate
    Source   : MC-86
    Criterion: The release-container workflow must include a test gate job that
               runs the full pytest suite and gates the container build — the
               build job must not start unless tests pass.

    This test verifies:
    1. The workflow file .github/workflows/release-container.yml exists
    2. It contains a job that runs pytest
    3. The container build job depends on (needs) the test job
    """
    # The workflow file must exist
    assert WORKFLOW_FILE.exists(), (
        f"Workflow file {WORKFLOW_FILE.relative_to(REPO_ROOT)} does not exist. "
        "CI container publish workflow has not been created yet."
    )

    workflow = yaml.safe_load(WORKFLOW_FILE.read_text())
    jobs = workflow.get("jobs", {})

    # Find a test gate job — a job whose steps include running pytest
    test_job_name = None
    for job_name, job_config in jobs.items():
        steps = job_config.get("steps", [])
        for step in steps:
            run_cmd = step.get("run", "")
            if "pytest" in run_cmd:
                test_job_name = job_name
                break
        if test_job_name:
            break

    assert test_job_name is not None, (
        "No job in the workflow runs pytest. "
        "A test gate job is required before container build."
    )

    # Find the container build job and verify it depends on the test job
    build_job_name = None
    for job_name, job_config in jobs.items():
        if job_name == test_job_name:
            continue
        steps = job_config.get("steps", [])
        for step in steps:
            run_cmd = step.get("run", "")
            if "podman build" in run_cmd or "buildah" in run_cmd or "docker build" in run_cmd:
                build_job_name = job_name
                break
        if build_job_name:
            break

    assert build_job_name is not None, (
        "No container build job found in the workflow."
    )

    build_job = jobs[build_job_name]
    needs = build_job.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]

    assert test_job_name in needs, (
        f"Build job '{build_job_name}' does not depend on test job '{test_job_name}'. "
        f"needs={needs}. The build must be gated by passing tests."
    )


@pytest.mark.integration
def test_mc_86_ci_container_publish_container_build_push_acceptance() -> None:
    """Acceptance test for slice: container-build-push.

    Feature  : MC-86-ci-container-publish
    Slice    : container-build-push
    Source   : MC-86
    Criterion: The workflow must build the container image and push it to
               quay.io/rhn_support_dsquirre/mc-container:latest, triggered
               on version release (tag push or GitHub release event).

    This test verifies:
    1. The workflow is triggered on release/tag events
    2. A job builds the container using the project Containerfile
    3. The job pushes to quay.io/rhn_support_dsquirre/mc-container
    """
    assert WORKFLOW_FILE.exists(), (
        f"Workflow file {WORKFLOW_FILE.relative_to(REPO_ROOT)} does not exist. "
        "CI container publish workflow has not been created yet."
    )

    workflow = yaml.safe_load(WORKFLOW_FILE.read_text())

    # Verify trigger is on release or version tag
    trigger = workflow.get(True, {})  # 'on' is parsed as True in YAML
    if not trigger:
        trigger = workflow.get("on", {})

    has_release_trigger = False
    if isinstance(trigger, dict):
        if "release" in trigger or "push" in trigger:
            has_release_trigger = True
            # If push trigger, verify it's scoped to version tags
            if "push" in trigger and "release" not in trigger:
                push_config = trigger["push"]
                tags = push_config.get("tags", [])
                assert any("v" in t for t in tags), (
                    "Push trigger exists but is not scoped to version tags (e.g., v*)."
                )

    assert has_release_trigger, (
        "Workflow is not triggered on release or version tag push events. "
        "Container publish must be automated on version releases."
    )

    # Verify a job pushes to quay.io
    jobs = workflow.get("jobs", {})
    push_found = False
    registry_url = "quay.io/rhn_support_dsquirre/mc-container"

    for job_name, job_config in jobs.items():
        steps = job_config.get("steps", [])
        for step in steps:
            run_cmd = step.get("run", "")
            if registry_url in run_cmd and ("push" in run_cmd or "podman push" in run_cmd):
                push_found = True
                break
        if push_found:
            break

    assert push_found, (
        f"No job step pushes to {registry_url}. "
        "The workflow must push the built image to the quay.io registry."
    )


@pytest.mark.integration
def test_mc_86_ci_container_publish_verify_docs_acceptance() -> None:
    """Acceptance test for slice: verify-docs.

    Feature  : MC-86-ci-container-publish
    Slice    : verify-docs
    Source   : MC-86
    Criterion: CLAUDE.md must document the automated CI container publish
               pipeline, indicating that container builds and pushes are
               handled by GitHub Actions on release, not manually.

    This test verifies:
    1. CLAUDE.md references the GitHub Actions workflow for container publishing
    2. The documentation explains the automated trigger mechanism
    """
    claude_md = REPO_ROOT / "CLAUDE.md"
    assert claude_md.exists(), "CLAUDE.md not found at repo root."

    content = claude_md.read_text().lower()

    # Documentation must mention CI/GitHub Actions for container publishing
    assert "github actions" in content or "github action" in content, (
        "CLAUDE.md does not mention GitHub Actions. "
        "Documentation must describe the automated CI container publish pipeline."
    )

    # Documentation must connect CI to container publishing
    has_ci_container_ref = (
        ("ci" in content or "github actions" in content or "workflow" in content)
        and ("container" in content or "image" in content)
        and ("release" in content or "publish" in content or "automat" in content)
    )
    assert has_ci_container_ref, (
        "CLAUDE.md does not document the automated container publish pipeline. "
        "It should explain that container builds are automated via GitHub Actions on release."
    )


@pytest.mark.integration
def test_quay_creds_refresh_regression() -> None:
    """Regression test for MC-206: QUAY_USERNAME and QUAY_PASSWORD secrets missing.

    Feature  : MC-206-quay-creds-refresh
    Slice    : secrets-configured
    Source   : MC-206
    Criterion: The GitHub Actions secrets QUAY_USERNAME and QUAY_PASSWORD must both
               be set in the repo's Actions secrets so that the release-container
               workflow can authenticate to quay.io and push the container image.

    Bug: The release-container workflow's `podman login quay.io` step receives empty
    strings for both username and password because the secrets were never configured,
    producing:
        Error: getting username and password: reading username: EOF

    This test verifies:
    1. `gh secret list --app actions` succeeds (gh CLI is authenticated)
    2. QUAY_USERNAME appears in the Actions secrets list
    3. QUAY_PASSWORD appears in the Actions secrets list
    """
    result = subprocess.run(
        ["gh", "secret", "list", "--app", "actions"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"gh secret list failed (exit {result.returncode}). "
        f"Ensure gh CLI is authenticated and has repo access.\n"
        f"stderr: {result.stderr.strip()}"
    )

    secret_names = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]

    assert "QUAY_USERNAME" in secret_names, (
        f"Secret QUAY_USERNAME is not configured in GitHub Actions secrets. "
        f"Found secrets: {secret_names}. "
        f"Without this secret, `podman login quay.io` receives an empty username "
        f"and fails with: Error: getting username and password: reading username: EOF. "
        f"Fix: gh secret set QUAY_USERNAME --body '<your-quay-robot-username>'"
    )

    assert "QUAY_PASSWORD" in secret_names, (
        f"Secret QUAY_PASSWORD is not configured in GitHub Actions secrets. "
        f"Found secrets: {secret_names}. "
        f"Without this secret, `podman login quay.io` receives an empty password "
        f"and fails with: Error: getting username and password: reading username: EOF. "
        f"Fix: gh secret set QUAY_PASSWORD --body '<your-quay-robot-token>'"
    )
