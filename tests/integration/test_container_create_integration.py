"""Integration test for container creation with real Podman."""

import json
import os
import platform
import subprocess
import tempfile

import pytest

from mc.container.manager import (
    ContainerManager,
    get_claude_global_config_path,
    get_ocm_config_path,
)
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


def _podman_available() -> bool:
    """Check if Podman is available and accessible.

    Returns:
        bool: True if Podman can be reached, False otherwise
    """
    try:
        client = PodmanClient()
        return client.ping()
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_create_container_e2e():
    """End-to-end test: create container, verify it exists, cleanup.

    Tests the entire stack:
    - PodmanClient connection
    - ContainerManager.create() with real Podman
    - StateDatabase persistence
    - Container configuration (userns_mode, volumes, labels)
    """
    # Setup temporary workspace and database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        # Initialize clients
        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            # Create container
            container = manager.create("99999999", workspace_path, "TestCustomer")

            # Verify container exists and is running
            assert container.status == "running", f"Expected running, got {container.status}"
            assert "mc.managed" in container.labels, "Missing mc.managed label"
            assert container.labels["mc.case_number"] == "99999999", "Case number mismatch"
            assert container.labels["mc.customer"] == "TestCustomer", "Customer name mismatch"

            # Verify container configuration
            # userns_mode verification (platform-dependent)
            if platform.system() == "Darwin":
                # macOS: Podman machine VM may default to "private" mode
                # This is a known limitation of running in a VM
                expected_userns = "private"
            else:
                # Linux: keep-id should work as expected
                expected_userns = "keep-id"

            assert container.attrs["HostConfig"]["UsernsMode"] == expected_userns, (
                f"Expected userns_mode={expected_userns}, got {container.attrs['HostConfig']['UsernsMode']}"
            )

            # Volume mount verification
            mounts = container.attrs["Mounts"]
            assert any(m["Destination"] == "/case" for m in mounts), "Missing /case mount"

            case_mount = next(m for m in mounts if m["Destination"] == "/case")
            assert case_mount["Source"] == workspace_path, (
                f"Mount source mismatch: expected {workspace_path}, got {case_mount['Source']}"
            )
            # Mode field may be empty on macOS Podman machine
            if case_mount.get("Mode"):
                assert case_mount["Mode"] == "rw", f"Expected rw mode, got {case_mount['Mode']}"

            # Verify state database updated
            metadata = state_db.get_container("99999999")
            assert metadata is not None, "Container not found in state database"
            assert metadata.container_id == container.id, "Container ID mismatch in state"
            assert metadata.workspace_path == workspace_path, "Workspace path mismatch in state"

            # Test auto-restart: stop container and verify it restarts on next access
            container.stop(timeout=2)  # type: ignore[no-untyped-call]

            # Wait for container to stop
            import time
            time.sleep(1)

            # Re-create (should auto-restart)
            restarted_container = manager.create("99999999", workspace_path, "TestCustomer")
            assert restarted_container.id == container.id, "Different container created instead of restart"
            # Reload container to get fresh status after restart
            restarted_container.reload()  # type: ignore[no-untyped-call]
            assert restarted_container.status == "running", "Container not running after restart"

        finally:
            # Cleanup: stop and remove container
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass  # Ignore cleanup errors

            # Clean up state
            try:
                state_db.delete_container("99999999")
            except Exception:
                pass


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_claude_vertex_creds_in_container_regression():
    """Regression test for GCP Vertex AI credentials not forwarded into container.

    Bug discovered: 2026-03-26
    Platform: Both
    Severity: major
    Source: ad-hoc

    Problem:
    ContainerManager.create() did not forward GCP Vertex AI authentication env vars
    (CLAUDE_CODE_USE_VERTEX, CLOUD_ML_REGION, ANTHROPIC_VERTEX_PROJECT_ID) from the
    host environment into the container. The ADC credentials file was also not mounted.
    As a result, `claude` inside the container triggered the setup/auth routine instead
    of running, because it had no credentials or Vertex configuration available.

    Steps to reproduce:
    1. Set CLAUDE_CODE_USE_VERTEX=1, CLOUD_ML_REGION=us-east5,
       ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project on the host.
    2. Run `mc case 12345678` to start a container.
    3. Inside the container, run `claude` — it prompts for auth setup.

    Expected: CLAUDE_CODE_USE_VERTEX, CLOUD_ML_REGION, and ANTHROPIC_VERTEX_PROJECT_ID
              are present in the container environment; `claude` starts without auth prompts.
    Actual:   Env vars are absent inside the container; `claude` prompts for auth setup.

    This test ensures the bug does not regress.
    """
    # Use a dedicated case number unlikely to conflict with other tests
    case_number = "55551111"
    container_name = f"mc-{case_number}"

    # PRE-TEST CLEANUP: Remove any stale container from previous runs
    subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)

    # Simulate host environment with Vertex credentials set
    test_env_vars = {
        "CLAUDE_CODE_USE_VERTEX": "1",
        "CLOUD_ML_REGION": "us-east5",
        "ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project",
    }
    for key, value in test_env_vars.items():
        os.environ[key] = value

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            container = manager.create(case_number, workspace_path, "VertexTest")

            # Verify env vars are set INSIDE the container via podman exec.
            # This is the correct assertion depth for a host→container boundary bug:
            # checking the Python object that was supposed to produce the artifact
            # is not enough — we must verify the end state inside a real container.
            result = subprocess.run(
                [
                    "podman",
                    "exec",
                    container_name,
                    "bash",
                    "-c",
                    "echo CLAUDE_CODE_USE_VERTEX=$CLAUDE_CODE_USE_VERTEX; "
                    "echo CLOUD_ML_REGION=$CLOUD_ML_REGION; "
                    "echo ANTHROPIC_VERTEX_PROJECT_ID=$ANTHROPIC_VERTEX_PROJECT_ID",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"podman exec failed: {result.stderr}"

            assert "CLAUDE_CODE_USE_VERTEX=1" in result.stdout, (
                f"CLAUDE_CODE_USE_VERTEX not forwarded into container. "
                f"Container env output:\n{result.stdout}"
            )
            assert "CLOUD_ML_REGION=us-east5" in result.stdout, (
                f"CLOUD_ML_REGION not forwarded into container. "
                f"Container env output:\n{result.stdout}"
            )
            assert "ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project" in result.stdout, (
                f"ANTHROPIC_VERTEX_PROJECT_ID not forwarded into container. "
                f"Container env output:\n{result.stdout}"
            )

        finally:
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
            subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)
            for key in test_env_vars:
                os.environ.pop(key, None)


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_reconciliation_with_real_podman():
    """Test reconciliation detects externally deleted containers.

    Verifies that state reconciliation correctly detects when a container
    is deleted outside the ContainerManager (e.g., via 'podman rm').
    """
    # PRE-TEST CLEANUP: Remove any stale containers from previous runs
    subprocess.run(["podman", "rm", "-f", "mc-77777777"], capture_output=True)
    subprocess.run(["podman", "rm", "-f", "mc-88888888"], capture_output=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            # Create container
            container = manager.create("88888888", workspace_path, "ReconcileTest")

            # Verify state has the container
            metadata = state_db.get_container("88888888")
            assert metadata is not None

            # Delete container externally (bypass ContainerManager)
            container.stop(timeout=2)  # type: ignore[no-untyped-call]
            container.remove()  # type: ignore[no-untyped-call]
            container = None

            # Trigger reconciliation by creating a new container
            new_container = manager.create("77777777", workspace_path, "NewContainer")

            # Verify old container removed from state (reconciliation worked)
            metadata = state_db.get_container("88888888")
            assert metadata is None, "Reconciliation failed to remove externally deleted container"

            # Verify new container was created successfully
            assert new_container.status == "running"

            # Cleanup new container
            new_container.stop(timeout=2)  # type: ignore[no-untyped-call]
            new_container.remove()  # type: ignore[no-untyped-call]
            state_db.delete_container("77777777")

        finally:
            # Cleanup: Force remove containers even if test failed
            subprocess.run(["podman", "rm", "-f", "mc-77777777"], capture_output=True)
            subprocess.run(["podman", "rm", "-f", "mc-88888888"], capture_output=True)

            # Also remove from state DB
            try:
                if state_db:
                    state_db.delete_container("77777777")
                    state_db.delete_container("88888888")
            except Exception:
                pass


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_agent_auth_mount_regression():
    """Regression test for MC-64: ~/mc/auth/ not volume-mounted into container.

    Bug discovered: 2026-05-12
    Platform: Both
    Severity: major
    Source: MC-64

    Problem:
    ContainerManager.create() builds volume mounts for ~/mc/config (ro) and
    ~/mc/state (rw), but omits ~/mc/auth/. Inside the container, auth.py defines
    TOKEN_CACHE_PATH = ~/mc/auth/token. When agent code calls save_token_cache(),
    the directory /home/mcuser/mc/auth/ does not exist as a host-mounted volume,
    causing: [Errno 13] Permission denied: '/home/mcuser/mc/auth'

    Steps to reproduce:
    1. Run `mc case 12345678` to create a container.
    2. Inside the container, attempt to write to /home/mcuser/mc/auth/token.
    3. The write fails because ~/mc/auth/ is not volume-mounted from the host.

    Expected: /home/mcuser/mc/auth/ is a host-mounted volume (rw) inside the
              container, so auth.py can persist token cache across container
              recreations.
    Actual:   /home/mcuser/mc/auth/ is not volume-mounted; writes fail with
              Permission denied or the token cache is lost on container recreation.

    This test ensures the bug does not regress.
    """
    case_number = "55550064"
    container_name = f"mc-{case_number}"

    # PRE-TEST CLEANUP: Remove any stale container from previous runs
    subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            container = manager.create(case_number, workspace_path, "AuthMountTest")

            # Verify that /home/mcuser/mc/auth/ is a host-mounted volume inside
            # the container. This is the correct assertion depth for a
            # host->container boundary bug: we must check the actual in-container
            # state via podman exec, not just the Python object.
            mount_result = subprocess.run(
                [
                    "podman", "exec", container_name,
                    "bash", "-c",
                    "mount | grep '/home/mcuser/mc/auth' || echo 'NOT_MOUNTED'"
                ],
                capture_output=True,
                text=True,
            )

            assert "NOT_MOUNTED" not in mount_result.stdout, (
                "/home/mcuser/mc/auth/ is NOT volume-mounted from the host. "
                "auth.py TOKEN_CACHE_PATH will not persist across container "
                "recreations and may fail with Permission denied.\n"
                f"Mount output: {mount_result.stdout}"
            )

        finally:
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
            subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_claude_container_settings_regression():
    """Regression test for MC-74: ~/.claude.json not mounted into container.

    Bug discovered: 2026-05-19
    Platform: Both
    Severity: minor
    Source: MC-74

    Problem:
    ContainerManager.create() mounts ~/.claude/ (directory) but NOT ~/.claude.json
    (file at HOME root). This file contains hasCompletedOnboarding and
    hasTrustDialogAccepted state. Without it mounted, each new container forces
    Claude Code to re-run the onboarding wizard and trust dialog on every launch.

    Steps to reproduce:
    1. Ensure ~/.claude.json exists on the host with hasCompletedOnboarding: true.
    2. Run `mc case 12345678` to create a new container.
    3. Inside the container, check for /home/mcuser/.claude.json.
    4. The file does not exist as a host mount — Claude Code prompts for onboarding.

    Expected: /home/mcuser/.claude.json is mounted read-only from the host, so
              Claude Code skips onboarding and trust dialogs in new containers.
    Actual:   /home/mcuser/.claude.json is NOT mounted; Claude Code asks "What text
              style do you prefer?" and "Do you trust the files?" on every launch.

    This test ensures the bug does not regress.
    """
    case_number = "55550074"
    container_name = f"mc-{case_number}"

    # PRE-TEST CLEANUP
    subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            container = manager.create(case_number, workspace_path, "ClaudeJsonTest")

            # Check if ~/.claude.json is mounted inside the container.
            # For host->container boundary bugs, we MUST verify in-container state
            # via podman exec — checking the Python volumes dict is not enough.
            result = subprocess.run(
                [
                    "podman", "exec", container_name,
                    "bash", "-c",
                    "test -f /home/mcuser/.claude.json && echo 'MOUNTED' || echo 'NOT_MOUNTED'"
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"podman exec failed: {result.stderr}"

            # This assertion should FAIL because the file is not currently mounted.
            assert result.stdout.strip() == "MOUNTED", (
                "/home/mcuser/.claude.json is NOT mounted inside the container. "
                "Claude Code will force re-onboarding on every container launch. "
                f"Output: {result.stdout.strip()}"
            )

        finally:
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
            subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_mc_79_ocm_config_readonly_mount_regression():
    """Regression test for MC-79: OCM config file mounted read-only into container.

    Bug discovered: 2026-05-20
    Platform: Both
    Severity: major
    Source: MC-79

    Problem:
    ContainerManager.create() bind-mounts the host OCM config file (ocm.json) into
    the container with mode "ro" (read-only). The OCM CLI needs to write token
    refreshes back to ocm.json during normal operation. When it attempts to save
    the refreshed token, it fails with:
      Error: Can't save config file: can't write file
             '/home/mcuser/.config/ocm/ocm.json': read-only file system

    Steps to reproduce:
    1. Ensure ~/.config/ocm/ocm.json (or macOS equivalent) exists on the host.
    2. Run `mc case 12345678` to create a container.
    3. Inside the container, run any OCM command that triggers a token refresh.
    4. OCM CLI fails with "read-only file system" when saving the refreshed token.

    Expected: The OCM config file is mounted read-write (rw) inside the container,
              allowing OCM CLI to persist token refreshes to disk.
    Actual:   The OCM config file is mounted read-only (ro); any write attempt
              from OCM CLI fails with "read-only file system".

    This test ensures the bug does not regress.
    """
    case_number = "55550079"
    container_name = f"mc-{case_number}"

    # PRE-TEST CLEANUP
    subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)

    # Ensure the host OCM config exists (create a temp one if needed)
    ocm_config = get_ocm_config_path()
    created_ocm_dir = False
    created_ocm_file = False

    if not ocm_config.parent.exists():
        ocm_config.parent.mkdir(parents=True, exist_ok=True)
        created_ocm_dir = True
    if not ocm_config.exists():
        ocm_config.write_text('{"access_token": "test", "refresh_token": "test"}')
        created_ocm_file = True

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            container = manager.create(case_number, workspace_path, "OcmMountTest")

            # Verify via podman exec that the OCM config file is writable inside
            # the container. This is the correct assertion depth for a
            # host->container boundary bug: we must check actual in-container
            # state, not just the Python volumes dict.
            result = subprocess.run(
                [
                    "podman", "exec", container_name,
                    "bash", "-c",
                    # Attempt to append to ocm.json — fails if read-only
                    "echo '' >> /home/mcuser/.config/ocm/ocm.json "
                    "&& echo 'WRITABLE' || echo 'READ_ONLY'"
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"podman exec failed: {result.stderr}"

            assert "WRITABLE" in result.stdout, (
                "OCM config file is NOT writable inside the container. "
                "OCM CLI cannot persist token refreshes. "
                f"Output: {result.stdout.strip()} "
                f"Stderr: {result.stderr.strip()}"
            )

        finally:
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
            subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)

            # Clean up temp OCM config if we created it
            if created_ocm_file and ocm_config.exists():
                ocm_config.unlink()
            if created_ocm_dir and ocm_config.parent.exists():
                try:
                    ocm_config.parent.rmdir()
                except OSError:
                    pass


def _get_host_timezone() -> str:
    """Detect the host timezone as an IANA tz name (e.g. 'Australia/Brisbane').

    Checks TZ env var first, then falls back to /etc/localtime symlink.
    Returns 'UTC' only if the host truly cannot determine its timezone.
    """
    tz = os.environ.get("TZ")
    if tz:
        return tz

    # macOS and Linux: /etc/localtime is typically a symlink into zoneinfo
    try:
        link = os.path.realpath("/etc/localtime")
        for marker in ("zoneinfo/",):
            idx = link.find(marker)
            if idx != -1:
                return link[idx + len(marker):]
    except Exception:
        pass

    return "UTC"


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_mc_107_container_timezone_regression():
    """Regression test for MC-107: container uses UTC instead of host timezone.

    Bug discovered: 2026-07-13
    Platform: Both
    Severity: major
    Source: MC-107

    Problem:
    ContainerManager.create() builds the environment dict without a TZ variable.
    The RHEL 10 UBI container image defaults to UTC, so all timestamps inside the
    container (e.g. `date`, log entries, file modification times) show UTC regardless
    of the host's timezone setting.

    Steps to reproduce:
    1. On a host with a non-UTC timezone (e.g. Australia/Brisbane / AEST).
    2. Run `mc case 12345678` to create a container.
    3. Inside the container, run `date`.
    4. Output shows UTC time instead of AEST.

    Expected: Container TZ environment variable is set to the host's timezone
              (e.g. 'Australia/Brisbane'), so timestamps match the host.
    Actual:   TZ is not set in the container; all timestamps default to UTC.

    This test ensures the bug does not regress.
    """
    host_tz = _get_host_timezone()
    assert host_tz != "UTC", (
        f"Host timezone is UTC -- cannot distinguish from bug. "
        f"This test must run on a host with a non-UTC timezone."
    )

    case_number = "55550107"
    container_name = f"mc-{case_number}"

    # PRE-TEST CLEANUP
    subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            container = manager.create(case_number, workspace_path, "TimezoneTest")

            # Check TZ env var inside the container via podman exec.
            # This is the correct assertion depth for a host->container boundary
            # bug: we must verify the actual in-container state, not just the
            # Python environment dict that was supposed to produce it.
            result = subprocess.run(
                [
                    "podman", "exec", container_name,
                    "bash", "-c", "echo TZ=$TZ",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"podman exec failed: {result.stderr}"

            # The container must have TZ set to the host timezone.
            assert f"TZ={host_tz}" in result.stdout, (
                f"Container TZ does not match host timezone.\n"
                f"Expected: TZ={host_tz}\n"
                f"Got:      {result.stdout.strip()}\n"
                f"Container is using UTC instead of host timezone."
            )

        finally:
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
            subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_mc_122_claude_json_rw_mount_corruption_regression():
    """Regression test for MC-122: rw bind-mount of ~/.claude.json causes host corruption.

    Bug discovered: 2026-07-14
    Platform: macOS (virtiofs), potentially Linux
    Severity: critical
    Source: MC-122

    Problem:
    ContainerManager.create() bind-mounts ~/.claude.json with mode "rw" into the
    container. On macOS/Podman with virtiofs, the container's file-caching layer
    can see a stale or truncated snapshot of the file. When Claude Code (or any
    process) inside the container writes back to /home/mcuser/.claude.json, the
    stale data overwrites the host's ~/.claude.json, corrupting it.

    The host file was observed overwritten with a 907-byte truncated version;
    Claude Code inside the container then hangs on the truncated invalid JSON.

    Steps to reproduce:
    1. Ensure ~/.claude.json exists on the host with valid JSON (e.g. 6 KB).
    2. Run `mc case 12345678` to create a container (mounts ~/.claude.json rw).
    3. Inside the container, any write to /home/mcuser/.claude.json propagates
       back to the host via the rw bind-mount.
    4. virtiofs caching desync causes the container to read a stale/truncated
       copy, which it then writes back, corrupting the host file.

    Expected: Writes to /home/mcuser/.claude.json inside the container do NOT
              propagate back to the host ~/.claude.json. The container gets an
              isolated copy of the file content (e.g. via podman cp or seed
              script), so Claude Code can read/write freely without risking
              host file corruption.
    Actual:   The rw bind-mount causes all container writes to propagate to the
              host file. virtiofs file-caching desync corrupts the host copy.

    This test ensures the bug does not regress.
    """
    claude_json = get_claude_global_config_path()
    if not claude_json.exists():
        pytest.skip("~/.claude.json does not exist on this host")

    case_number = "55550122"
    container_name = f"mc-{case_number}"

    # PRE-TEST CLEANUP
    subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)

    # Read the original host content before creating container
    original_content = claude_json.read_text()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            container = manager.create(case_number, workspace_path, "ClaudeJsonRWTest")

            # Write a canary marker to .claude.json INSIDE the container.
            # If the rw bind-mount is active, this write propagates to the host.
            canary = "MC122_CORRUPTION_CANARY"
            result = subprocess.run(
                [
                    "podman", "exec", container_name,
                    "bash", "-c",
                    f'python3 -c "'
                    f"import json, pathlib; "
                    f"p = pathlib.Path('/home/mcuser/.claude.json'); "
                    f"d = json.loads(p.read_text()) if p.exists() else {{}}; "
                    f"d['_mc122_canary'] = '{canary}'; "
                    f"p.write_text(json.dumps(d, indent=2)); "
                    f"print('CANARY_WRITTEN')"
                    f'"',
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, (
                f"podman exec failed: {result.stderr}"
            )
            assert "CANARY_WRITTEN" in result.stdout, (
                f"Failed to write canary inside container: {result.stdout} {result.stderr}"
            )

            # Now check the HOST file. If the canary is visible, the rw mount is
            # propagating container writes back to the host (= the bug).
            host_content = claude_json.read_text()
            host_data = json.loads(host_content)

            # The host file must NOT contain the canary. When the bug is present
            # (rw bind-mount), the canary WILL appear in the host file, so this
            # assertion FAILS -- confirming RED.
            assert "_mc122_canary" not in host_data, (
                "HOST ~/.claude.json was modified from inside the container! "
                "The rw bind-mount allows container writes to propagate to the "
                "host, creating a corruption vector via virtiofs file-caching "
                f"desync. Canary value found: {host_data.get('_mc122_canary')}"
            )

        finally:
            # Restore original host file content (undo canary injection)
            try:
                claude_json.write_text(original_content)
            except Exception:
                pass

            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
            subprocess.run(["podman", "rm", "-f", container_name], capture_output=True)
