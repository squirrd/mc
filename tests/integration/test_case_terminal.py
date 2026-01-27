"""Integration test for case terminal command.

Tests the end-to-end terminal attachment workflow with real components.
Skipped unless Podman and Salesforce are available.
"""

import os
import tempfile

import pytest

from mc.config.manager import ConfigManager
from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient
from mc.integrations.salesforce_api import SalesforceAPIClient
from mc.terminal.attach import attach_terminal


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


def _salesforce_configured() -> bool:
    """Check if Salesforce credentials are configured.

    Returns:
        bool: True if credentials present in config, False otherwise
    """
    try:
        config = ConfigManager()
        if not config.exists():
            return False

        cfg = config.load()
        sf_config = cfg.get("salesforce", {})

        return all([
            sf_config.get("username"),
            sf_config.get("password"),
            sf_config.get("security_token"),
        ])
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available"
)
@pytest.mark.skipif(
    not _salesforce_configured(),
    reason="Salesforce credentials not configured"
)
def test_case_terminal_end_to_end(mocker):
    """End-to-end test: terminal attachment workflow.

    Tests the entire stack:
    - Salesforce API integration (case metadata fetch)
    - Container auto-creation if missing
    - Bashrc generation with case metadata
    - Terminal launcher invocation

    Note: This test mocks the terminal launcher to avoid actually
    launching windows, but exercises all other real components.
    """
    # Setup temporary database and workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        # Initialize real components
        config = ConfigManager()
        cfg = config.load()

        sf_config = cfg.get("salesforce", {})
        salesforce_client = SalesforceAPIClient(
            username=sf_config["username"],
            password=sf_config["password"],
            security_token=sf_config["security_token"],
        )

        podman_client = PodmanClient()
        state_db = StateDatabase(db_path)
        container_manager = ContainerManager(podman_client, state_db)

        # Mock terminal launcher to avoid actually launching windows
        mock_launcher = mocker.MagicMock()
        mocker.patch("mc.terminal.attach.get_launcher", return_value=mock_launcher)

        # Mock TTY check (tests run in non-TTY environments)
        mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

        # Override config base_directory for test
        mocker.patch.object(config, "load", return_value={"base_directory": tmpdir})

        # Use test case number that won't conflict
        test_case_number = "99999999"
        container_name = f"mc-{test_case_number}"

        container = None
        try:
            # Execute terminal attachment workflow
            attach_terminal(
                case_number=test_case_number,
                config_manager=config,
                salesforce_client=salesforce_client,
                container_manager=container_manager,
            )

            # Verify terminal launcher was called
            mock_launcher.launch.assert_called_once()

            # Verify launch options
            call_args = mock_launcher.launch.call_args
            launch_options = call_args[0][0]

            # Verify window title format
            assert test_case_number in launch_options.title
            assert " - " in launch_options.title  # Format: "case - customer - description"

            # Verify podman exec command
            command = launch_options.command
            assert "podman exec -it" in command
            assert container_name in command
            assert "/bin/bash" in command
            assert "BASH_ENV=" in command  # Custom bashrc injection
            assert f"PS1=[MC-{test_case_number}]" in command  # Custom prompt

            # Verify container was created (attach_terminal auto-creates if missing)
            # Get container from Podman
            try:
                container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]

                # Verify container is running
                assert container.status in ("running", "configured"), (
                    f"Expected running/configured, got {container.status}"
                )

                # Verify container labels
                assert "mc.managed" in container.labels
                assert container.labels["mc.case_number"] == test_case_number

            except Exception as e:
                pytest.fail(f"Container not found or invalid: {e}")

            # Verify state database updated
            metadata = state_db.get_container(test_case_number)
            assert metadata is not None, "Container not in state database"
            assert metadata.case_number == test_case_number
            assert metadata.workspace_path is not None

        finally:
            # Cleanup: stop and remove container
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass  # Ignore cleanup errors

            # Try cleanup by name if container object not available
            try:
                cleanup_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
                cleanup_container.stop(timeout=2)  # type: ignore[no-untyped-call]
                cleanup_container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass  # Container already cleaned up
