"""Integration tests for mc-rhel10 container image functionality.

These tests verify end-to-end container creation, environment setup, and
runtime capabilities using the mc-rhel10 RHEL 10 UBI image.
"""

import os
import tempfile
from pathlib import Path

import pytest

from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_state_db():
    """Create temporary in-memory state database."""
    db = StateDatabase(":memory:")
    yield db


@pytest.fixture
def podman_client():
    """Create PodmanClient instance."""
    return PodmanClient()


@pytest.fixture
def container_manager(podman_client, temp_state_db):
    """Create ContainerManager instance with temporary state."""
    return ContainerManager(podman_client, temp_state_db)


@pytest.fixture
def cleanup_containers(podman_client):
    """Cleanup test containers after test completion."""
    containers_to_clean = []

    def register(container_id):
        containers_to_clean.append(container_id)

    yield register

    # Cleanup
    for container_id in containers_to_clean:
        try:
            container = podman_client.client.containers.get(container_id)
            container.stop(timeout=2)  # type: ignore[no-untyped-call]
            container.remove()  # type: ignore[no-untyped-call]
        except Exception:
            pass  # Container already deleted


def check_image_exists(podman_client):
    """Check if mc-rhel10:latest image exists."""
    try:
        podman_client.client.images.get("mc-rhel10:latest")
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestContainerImageExists:
    """Test mc-rhel10 image availability."""

    def test_image_exists(self, podman_client):
        """Test that mc-rhel10:latest image exists and is accessible."""
        if not check_image_exists(podman_client):
            pytest.skip(
                "mc-rhel10:latest image not found. "
                "Run: podman build -t mc-rhel10:latest -f container/Containerfile ."
            )

        # Verify image exists
        image = podman_client.client.images.get("mc-rhel10:latest")
        assert image is not None

        # Verify image has expected labels
        labels = image.labels  # type: ignore[attr-defined]
        assert labels.get("description") == "RHEL 10 UBI container with MC CLI and essential tools for Red Hat case work"
        assert labels.get("version") == "2.0"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestContainerCreation:
    """Test container creation with mc-rhel10 image."""

    def test_create_container_with_mc_rhel10(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Test creating container using mc-rhel10:latest image."""
        if not check_image_exists(podman_client):
            pytest.skip("mc-rhel10:latest image not found")

        # Create container
        container = container_manager.create(
            case_number="99999999",
            workspace_path=temp_workspace,
            customer_name="Integration Test Customer"
        )
        cleanup_containers(container.id)  # type: ignore[attr-defined]

        # Verify container created
        assert container is not None
        assert container.status == "running"  # type: ignore[attr-defined]

        # Verify image is mc-rhel10:latest
        container_image = container.image.tags[0]  # type: ignore[attr-defined]
        assert "mc-rhel10:latest" in container_image

        # Verify workspace mounted
        mounts = container.attrs.get("Mounts", [])  # type: ignore[attr-defined]
        workspace_mount = next((m for m in mounts if m["Destination"] == "/case"), None)
        assert workspace_mount is not None
        assert workspace_mount["Source"] == temp_workspace


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestEnvironmentVariables:
    """Test environment variables set correctly in container."""

    def test_environment_variables_set(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Test that environment variables are set correctly in container."""
        if not check_image_exists(podman_client):
            pytest.skip("mc-rhel10:latest image not found")

        # Create container with specific metadata
        container = container_manager.create(
            case_number="88888888",
            workspace_path=temp_workspace,
            customer_name="ACME Corporation"
        )
        cleanup_containers(container.id)  # type: ignore[attr-defined]

        # Execute env command to get environment variables
        exit_code, output = container.exec_run(  # type: ignore[attr-defined]
            cmd=["bash", "-c", "env | grep -E '^(MC_|CASE_|CUSTOMER_|WORKSPACE_)' | sort"],
            stdout=True,
            stderr=True
        )

        assert exit_code == 0
        output_str = output.decode("utf-8")

        # Verify environment variables
        assert "CASE_NUMBER=88888888" in output_str
        assert "CUSTOMER_NAME=ACME Corporation" in output_str
        assert "WORKSPACE_PATH=/case" in output_str
        assert "MC_RUNTIME_MODE=agent" in output_str


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestShellCustomization:
    """Test shell prompt customization."""

    def test_shell_prompt_format(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Test that PS1 prompt is set correctly via entrypoint."""
        if not check_image_exists(podman_client):
            pytest.skip("mc-rhel10:latest image not found")

        # Create container
        container = container_manager.create(
            case_number="77777777",
            workspace_path=temp_workspace,
            customer_name="Test Customer"
        )
        cleanup_containers(container.id)  # type: ignore[attr-defined]

        # Check PS1 environment variable (set by entrypoint.sh)
        exit_code, output = container.exec_run(  # type: ignore[attr-defined]
            cmd=["bash", "-c", "echo $PS1"],
            stdout=True,
            stderr=True
        )

        assert exit_code == 0
        ps1 = output.decode("utf-8").strip()

        # Verify prompt contains case number in [case-XXXXXXXX] format
        assert "case-77777777" in ps1


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestMCCLIAccessibility:
    """Test MC CLI accessible inside container."""

    def test_mc_cli_importable(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Test that MC CLI is installed and importable inside container."""
        if not check_image_exists(podman_client):
            pytest.skip("mc-rhel10:latest image not found")

        # Create container
        container = container_manager.create(
            case_number="66666666",
            workspace_path=temp_workspace,
            customer_name="Test Customer"
        )
        cleanup_containers(container.id)  # type: ignore[attr-defined]

        # Test importing mc module and getting version
        exit_code, output = container.exec_run(  # type: ignore[attr-defined]
            cmd=["python3", "-c", "import mc; from mc.version import get_version; print(get_version())"],
            stdout=True,
            stderr=True
        )

        assert exit_code == 0
        version = output.decode("utf-8").strip()
        assert len(version) > 0  # Version string should be non-empty
        assert "." in version  # Version should have format like "2.0.0"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestEssentialTools:
    """Test essential tools available in container."""

    def test_essential_tools_available(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Test that essential tools (vim, curl, openssl) are available."""
        if not check_image_exists(podman_client):
            pytest.skip("mc-rhel10:latest image not found")

        # Create container
        container = container_manager.create(
            case_number="55555555",
            workspace_path=temp_workspace,
            customer_name="Test Customer"
        )
        cleanup_containers(container.id)  # type: ignore[attr-defined]

        # Check for essential tools
        exit_code, output = container.exec_run(  # type: ignore[attr-defined]
            cmd=["bash", "-c", "which vim && which curl && which openssl && which wget"],
            stdout=True,
            stderr=True
        )

        assert exit_code == 0
        output_str = output.decode("utf-8")

        # Verify all tools found
        assert "/usr/bin/vim" in output_str or "/bin/vim" in output_str
        assert "/usr/bin/curl" in output_str or "/bin/curl" in output_str
        assert "/usr/bin/openssl" in output_str or "/bin/openssl" in output_str
        assert "/usr/bin/wget" in output_str or "/bin/wget" in output_str


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestRuntimeModeDetection:
    """Test runtime mode detection inside container."""

    def test_runtime_mode_agent_detected(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Test that runtime mode is detected as 'agent' inside container."""
        if not check_image_exists(podman_client):
            pytest.skip("mc-rhel10:latest image not found")

        # Create container
        container = container_manager.create(
            case_number="44444444",
            workspace_path=temp_workspace,
            customer_name="Test Customer"
        )
        cleanup_containers(container.id)  # type: ignore[attr-defined]

        # Test runtime mode detection
        exit_code, output = container.exec_run(  # type: ignore[attr-defined]
            cmd=["python3", "-c", "from mc.runtime import get_runtime_mode; assert get_runtime_mode() == 'agent'; print('OK')"],
            stdout=True,
            stderr=True
        )

        assert exit_code == 0
        assert "OK" in output.decode("utf-8")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestConfigFileAccess:
    """Test configuration file accessibility inside container."""

    def test_config_file_readable_if_mounted(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Test that config file is readable inside container when mounted."""
        if not check_image_exists(podman_client):
            pytest.skip("mc-rhel10:latest image not found")

        # Note: This test validates the container can read files
        # Config mounting is handled separately by Phase 10 config_mount.py
        # Here we just verify the container has read capabilities

        # Create a test config file in workspace
        config_content = """
[general]
base_directory = "/workspace"
"""
        config_path = Path(temp_workspace) / "test_config.toml"
        config_path.write_text(config_content)

        # Create container
        container = container_manager.create(
            case_number="33333333",
            workspace_path=temp_workspace,
            customer_name="Test Customer"
        )
        cleanup_containers(container.id)  # type: ignore[attr-defined]

        # Verify file is readable from mounted workspace
        exit_code, output = container.exec_run(  # type: ignore[attr-defined]
            cmd=["cat", "/case/test_config.toml"],
            stdout=True,
            stderr=True
        )

        assert exit_code == 0
        content = output.decode("utf-8")
        assert "base_directory" in content
        assert "/workspace" in content


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MC_TEST_INTEGRATION"),
    reason="Integration tests disabled (set MC_TEST_INTEGRATION=1 to enable)"
)
class TestImagePullAndTag:
    """Test automatic image pull from registry and tagging."""

    def test_image_pull_and_tag_regression(
        self, container_manager, temp_workspace, cleanup_containers, podman_client
    ):
        """Regression test for UAT 3.1 - Image pull and tag failure.

        Bug discovered: 2026-02-04
        Platform: macOS (reproduced), likely affects all platforms
        Severity: Critical - Blocks core functionality when image not cached

        Problem:
        When mc-rhel10:latest image is not available locally, the code attempts
        to pull from quay.io/rhn_support_dsquirre/mc-container:latest and tag it
        as mc-rhel10:latest. However, the tagging fails with:

        "Image.tag() missing 1 required positional argument: 'tag'"

        Root cause:
        src/mc/container/manager.py:201 calls:
        ```python
        pulled_image.tag(image_name)  # image_name = "mc-rhel10:latest"
        ```

        But the Podman SDK's image.tag() method requires TWO arguments:
        ```python
        image.tag(repository, tag)  # Should be: ("mc-rhel10", "latest")
        ```

        The image_name "mc-rhel10:latest" needs to be split into repository
        and tag components before calling tag().

        Steps to reproduce:
        1. Remove both mc-rhel10:latest and quay.io/.../mc-container:latest
        2. Run: mc case 04347611
        3. Code pulls image successfully but fails to tag it
        4. Error: "Image.tag() missing 1 required positional argument: 'tag'"

        Expected:
        - Image pulled from quay.io registry
        - Image tagged as mc-rhel10:latest
        - Container created successfully

        Actual (before fix):
        - Image pulled successfully (visible in `podman images`)
        - Tagging fails with TypeError
        - Container creation fails
        - Confusing error message suggests building locally

        This test ensures image pull and tag workflow works correctly.

        UAT Test: 3.1 Missing Image - Clear Error Message
        Fixed in: TBD (test currently reproduces the bug)
        """
        # Backup: Check if images exist and back them up by listing their IDs
        local_image_id = None
        registry_image_id = None

        try:
            local_img = podman_client.client.images.get("mc-rhel10:latest")
            local_image_id = local_img.id  # type: ignore[attr-defined]
        except Exception:
            pass  # Image doesn't exist locally

        try:
            registry_img = podman_client.client.images.get(
                "quay.io/rhn_support_dsquirre/mc-container:latest"
            )
            registry_image_id = registry_img.id  # type: ignore[attr-defined]
        except Exception:
            pass  # Registry image not pulled yet

        # Remove both images to simulate fresh install scenario
        print("\nRemoving existing images to simulate fresh install...")
        try:
            podman_client.client.images.remove("mc-rhel10:latest", force=True)
            print("✓ Removed mc-rhel10:latest")
        except Exception:
            print("  (mc-rhel10:latest not found - already clean)")

        try:
            podman_client.client.images.remove(
                "quay.io/rhn_support_dsquirre/mc-container:latest", force=True
            )
            print("✓ Removed quay.io/.../mc-container:latest")
        except Exception:
            print("  (registry image not found - already clean)")

        try:
            # Verify clean slate
            with pytest.raises(Exception):
                podman_client.client.images.get("mc-rhel10:latest")

            # Execute: Create container (triggers _ensure_image which should pull and tag)
            print("\nAttempting to create container (should trigger image pull and tag)...")
            container = container_manager.create(
                case_number="99999998",
                workspace_path=temp_workspace,
                customer_name="UAT Test Customer"
            )
            cleanup_containers(container.id)  # type: ignore[attr-defined]

            # If we reach here, the bug is FIXED! Verify expected behavior:
            print("✓ Container created successfully!")

            # Verify image was pulled and tagged correctly
            local_image = podman_client.client.images.get("mc-rhel10:latest")
            assert local_image is not None, "mc-rhel10:latest should be tagged after pull"

            # Verify image tags include mc-rhel10:latest
            tags = local_image.tags  # type: ignore[attr-defined]
            assert any("mc-rhel10:latest" in tag for tag in tags), (
                f"Expected mc-rhel10:latest in tags, got: {tags}"
            )

            print("✓ Test PASSED: Image pull and tag workflow working correctly")
            print(f"  Image tags: {tags}")

        except RuntimeError as e:
            # If we get RuntimeError, check if it's the bug we're testing for
            error_msg = str(e)

            if "Image.tag() missing 1 required positional argument" in error_msg:
                pytest.fail(
                    f"✗ BUG REPRODUCED: Image pull succeeded but tag failed!\n"
                    f"Error: {error_msg}\n\n"
                    f"Root cause: src/mc/container/manager.py:201 calls:\n"
                    f"  pulled_image.tag(image_name)\n"
                    f"But should call:\n"
                    f"  pulled_image.tag(repository, tag)\n\n"
                    f"Fix: Split 'mc-rhel10:latest' into ('mc-rhel10', 'latest')\n"
                    f"Example:\n"
                    f"  repo, tag = image_name.split(':', 1) if ':' in image_name else (image_name, 'latest')\n"
                    f"  pulled_image.tag(repo, tag)\n"
                )
            else:
                # Some other error - re-raise for investigation
                raise

        finally:
            # Restore images if they were backed up
            # Note: We can't easily restore by ID without re-pulling
            # So we'll leave the pulled image in place (it's useful for other tests)
            print("\n[Test cleanup complete - pulled image left in place for other tests]")
