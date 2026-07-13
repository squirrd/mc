"""Unit tests for ContainerManager mount and pre-flight behavior (Phase 33)."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
import pytest
from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


def _make_manager():
    """Return a ContainerManager with minimal mocked dependencies."""
    podman_client = Mock(spec=PodmanClient)
    state_db = Mock(spec=StateDatabase)
    podman_client.client.containers.list.return_value = []
    state_db.get_container.return_value = None
    mock_image = MagicMock()
    podman_client.client.images.get.return_value = mock_image
    mock_container = MagicMock()
    mock_container.id = "abc123"
    mock_container.status = "running"
    podman_client.client.containers.create.return_value = mock_container
    return ContainerManager(podman_client, state_db), podman_client


class TestMcConfigMount:
    """Tests for ~/mc/config read-only mount."""

    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_mc_config_mounted_readonly_when_present(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path
    ):
        """mc/config is added to volumes dict with mode 'ro' when it exists."""
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        mock_claude_path.return_value = claude_dir

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/home/user/mc/config" in volumes
        assert volumes["/home/user/mc/config"]["bind"] == "/home/mcuser/mc/config"
        assert volumes["/home/user/mc/config"]["mode"] == "ro"

    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_create_raises_if_mc_config_missing(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path
    ):
        """RuntimeError raised before container creation when ~/mc/config absent."""
        mc_config = MagicMock()
        mc_config.exists.return_value = False
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        manager, podman = _make_manager()

        with pytest.raises(RuntimeError, match="MC config directory not found"):
            manager.create("12345678", "/workspace", "Customer")

        podman.client.containers.create.assert_not_called()


class TestClaudeDirMount:
    """Tests for ~/.claude read-write mount."""

    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_claude_dir_mounted_readwrite_when_present(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path
    ):
        """~/.claude is added to volumes dict with mode 'rw' when it exists."""
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = True
        claude_dir.__str__ = lambda self: "/home/user/.claude"
        mock_claude_path.return_value = claude_dir

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/home/user/.claude" in volumes
        assert volumes["/home/user/.claude"]["bind"] == "/home/mcuser/.claude"
        assert volumes["/home/user/.claude"]["mode"] == "rw"

    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_claude_dir_absent_from_volumes_when_missing(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path
    ):
        """~/.claude is not in volumes when the directory does not exist."""
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        claude_dir.__str__ = lambda self: "/home/user/.claude"
        mock_claude_path.return_value = claude_dir

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/home/user/.claude" not in volumes

    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_create_warns_and_continues_if_claude_dir_missing(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path, capsys
    ):
        """Warning printed but no error when ~/.claude is absent — container opens normally."""
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        claude_dir.__str__ = lambda self: "/home/user/.claude"
        mock_claude_path.return_value = claude_dir

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "claude" in captured.out.lower()
        podman.client.containers.create.assert_called_once()


class TestAuthMount:
    """Tests for ~/mc/auth read-write mount (MC-64 regression guard)."""

    @pytest.mark.backwards_compatibility
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_auth_dir_mounted_readwrite(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path
    ):
        """~/mc/auth is added to volumes dict with mode 'rw'.

        auth.py TOKEN_CACHE_PATH resolves to ~/mc/auth/token. Without this mount
        the container agent cannot read or write cached Red Hat SSO tokens, causing
        Permission denied errors and forcing re-authentication on every API call.
        """
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        mock_claude_path.return_value = claude_dir

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]

        # Find the auth mount — the host path is ~/mc/auth (Path.home() / "mc" / "auth")
        mc_auth_path = str(Path.home() / "mc" / "auth")
        assert mc_auth_path in volumes, (
            f"~/mc/auth/ is not volume-mounted. TOKEN_CACHE_PATH will not persist. "
            f"Volumes: {list(volumes.keys())}"
        )
        assert volumes[mc_auth_path]["bind"] == "/home/mcuser/mc/auth", (
            f"auth mount bind target is wrong. Got: {volumes[mc_auth_path]['bind']}"
        )
        assert volumes[mc_auth_path]["mode"] == "rw", (
            f"auth mount must be rw for token cache writes. Got: {volumes[mc_auth_path]['mode']}"
        )


class TestClaudeJsonMount:
    """Tests for ~/.claude.json mount (MC-74 presence guard, MC-108 rw mode)."""

    @pytest.mark.backwards_compatibility
    @patch('mc.container.manager.get_claude_global_config_path')
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_claude_json_mounted_readwrite_when_present(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path,
        mock_adc_path, mock_claude_json_path
    ):
        """~/.claude.json is added to volumes dict with mode 'rw' when it exists.

        This file contains hasCompletedOnboarding and hasTrustDialogAccepted state.
        Without it, each new container forces Claude Code re-onboarding.
        Must be rw so Claude Code can persist trust-prompt acceptance (MC-108).
        """
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        mock_claude_path.return_value = claude_dir

        adc = MagicMock()
        adc.exists.return_value = False
        mock_adc_path.return_value = adc

        claude_json = MagicMock()
        claude_json.exists.return_value = True
        claude_json.__str__ = lambda self: "/home/user/.claude.json"
        mock_claude_json_path.return_value = claude_json

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/home/user/.claude.json" in volumes, (
            f"~/.claude.json is not volume-mounted. "
            f"Volumes: {list(volumes.keys())}"
        )
        assert volumes["/home/user/.claude.json"]["bind"] == "/home/mcuser/.claude.json", (
            f"claude.json mount bind target is wrong. "
            f"Got: {volumes['/home/user/.claude.json']['bind']}"
        )
        assert volumes["/home/user/.claude.json"]["mode"] == "rw", (
            f"claude.json mount must be rw for trust-prompt persistence (MC-108). "
            f"Got: {volumes['/home/user/.claude.json']['mode']}"
        )

    @patch('mc.container.manager.get_claude_global_config_path')
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_claude_json_absent_from_volumes_when_missing(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path,
        mock_adc_path, mock_claude_json_path
    ):
        """~/.claude.json is not in volumes when the file does not exist."""
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        mock_claude_path.return_value = claude_dir

        adc = MagicMock()
        adc.exists.return_value = False
        mock_adc_path.return_value = adc

        claude_json = MagicMock()
        claude_json.exists.return_value = False
        claude_json.__str__ = lambda self: "/home/user/.claude.json"
        mock_claude_json_path.return_value = claude_json

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        # No key containing ".claude.json" should be present
        claude_json_keys = [k for k in volumes if ".claude.json" in k]
        assert len(claude_json_keys) == 0, (
            f"~/.claude.json should not be in volumes when absent. "
            f"Found: {claude_json_keys}"
        )


class TestAllMountsTogether:
    """Tests for workspace + mc/config + OCM + claude + claude.json combined mount scenarios."""

    @patch('mc.container.manager.get_claude_global_config_path')
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_all_mounts_present_when_all_paths_exist(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path,
        mock_adc_path, mock_claude_json_path
    ):
        """Workspace, mc/config, OCM, claude, and claude.json all mounted when all host paths exist."""
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = True
        ocm_config.__str__ = lambda self: "/home/user/.config/ocm/ocm.json"
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = True
        claude_dir.__str__ = lambda self: "/home/user/.claude"
        mock_claude_path.return_value = claude_dir

        # ADC absent — tested separately in TestVertexEnvForwarding
        adc = MagicMock()
        adc.exists.return_value = False
        mock_adc_path.return_value = adc

        claude_json = MagicMock()
        claude_json.exists.return_value = True
        claude_json.__str__ = lambda self: "/home/user/.claude.json"
        mock_claude_json_path.return_value = claude_json

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        mc_state_path = str(Path.home() / "mc" / "state")
        mc_auth_path = str(Path.home() / "mc" / "auth")
        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/workspace" in volumes
        assert "/home/user/mc/config" in volumes
        assert "/home/user/.config/ocm/ocm.json" in volumes
        assert "/home/user/.claude" in volumes
        assert "/home/user/.claude.json" in volumes
        assert mc_state_path in volumes
        assert mc_auth_path in volumes
        assert len(volumes) == 7


class TestVertexEnvForwarding:
    """Tests for GCP Vertex / Claude auth env var forwarding into container (backwards_compat)."""

    def _make_manager_with_paths(self, mc_config_path: str = "/home/user/mc/config"):
        """Return a ContainerManager with all path helpers patched."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)
        podman_client.client.containers.list.return_value = []
        state_db.get_container.return_value = None
        mock_image = MagicMock()
        podman_client.client.images.get.return_value = mock_image
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"
        podman_client.client.containers.create.return_value = mock_container
        return ContainerManager(podman_client, state_db), podman_client

    def _patch_paths(self, mc_exists=True, ocm_exists=False, claude_exists=False, adc_exists=False):
        """Return a dict of patches for all path helpers."""
        mc_config = MagicMock()
        mc_config.exists.return_value = mc_exists
        mc_config.__str__ = lambda self: "/home/user/mc/config"

        ocm_config = MagicMock()
        ocm_config.exists.return_value = ocm_exists
        ocm_config.__str__ = lambda self: "/home/user/.config/ocm/ocm.json"

        claude_dir = MagicMock()
        claude_dir.exists.return_value = claude_exists
        claude_dir.__str__ = lambda self: "/home/user/.claude"

        adc_path = MagicMock()
        adc_path.exists.return_value = adc_exists
        adc_path.__str__ = lambda self: "/home/user/.config/gcloud/application_default_credentials.json"

        return {
            'mc': mc_config,
            'ocm': ocm_config,
            'claude': claude_dir,
            'adc': adc_path,
        }

    @pytest.mark.backwards_compatibility
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    @patch.dict('os.environ', {
        'CLAUDE_CODE_USE_VERTEX': '1',
        'CLOUD_ML_REGION': 'us-east5',
        'ANTHROPIC_VERTEX_PROJECT_ID': 'my-gcp-project',
    })
    def test_vertex_env_vars_forwarded_when_set_in_host_env(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path, mock_adc_path
    ):
        """CLAUDE_CODE_USE_VERTEX, CLOUD_ML_REGION, ANTHROPIC_VERTEX_PROJECT_ID are forwarded
        into the container environment when they are set on the host.

        This is a backwards-compatibility regression guard: ContainerManager.create() must
        forward these env vars so that claude inside the container uses Vertex auth instead
        of prompting for setup.
        """
        paths = self._patch_paths(mc_exists=True, adc_exists=False)
        mock_mc_path.return_value = paths['mc']
        mock_ocm_path.return_value = paths['ocm']
        mock_claude_path.return_value = paths['claude']
        mock_adc_path.return_value = paths['adc']

        manager, podman = self._make_manager_with_paths()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        env = call_kwargs["environment"]

        assert env.get("CLAUDE_CODE_USE_VERTEX") == "1", (
            f"CLAUDE_CODE_USE_VERTEX not forwarded into container env. Got: {env}"
        )
        assert env.get("CLOUD_ML_REGION") == "us-east5", (
            f"CLOUD_ML_REGION not forwarded into container env. Got: {env}"
        )
        assert env.get("ANTHROPIC_VERTEX_PROJECT_ID") == "my-gcp-project", (
            f"ANTHROPIC_VERTEX_PROJECT_ID not forwarded into container env. Got: {env}"
        )

    @pytest.mark.backwards_compatibility
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    @patch.dict('os.environ', {}, clear=False)
    def test_vertex_env_vars_absent_from_env_when_not_set_on_host(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path, mock_adc_path
    ):
        """Vertex env vars are NOT injected when absent from host environment.

        Ensures that when the host has no Vertex config (e.g. users without GCP setup),
        the container environment dict does not contain unset keys.
        """
        import os as _os
        # Ensure vars are not set for this test
        for key in ('CLAUDE_CODE_USE_VERTEX', 'CLOUD_ML_REGION', 'ANTHROPIC_VERTEX_PROJECT_ID'):
            _os.environ.pop(key, None)

        paths = self._patch_paths(mc_exists=True, adc_exists=False)
        mock_mc_path.return_value = paths['mc']
        mock_ocm_path.return_value = paths['ocm']
        mock_claude_path.return_value = paths['claude']
        mock_adc_path.return_value = paths['adc']

        manager, podman = self._make_manager_with_paths()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        env = call_kwargs["environment"]

        assert "CLAUDE_CODE_USE_VERTEX" not in env or env.get("CLAUDE_CODE_USE_VERTEX") == "", (
            f"CLAUDE_CODE_USE_VERTEX should not be set when absent from host env. Got: {env}"
        )

    @pytest.mark.backwards_compatibility
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    @patch.dict('os.environ', {
        'CLAUDE_CODE_USE_VERTEX': '1',
        'CLOUD_ML_REGION': 'us-east5',
        'ANTHROPIC_VERTEX_PROJECT_ID': 'my-gcp-project',
    })
    def test_adc_file_mounted_readonly_when_present(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path, mock_adc_path
    ):
        """ADC credentials file is mounted ro at /gcp/creds.json when it exists on host.

        Also verifies GOOGLE_APPLICATION_CREDENTIALS is set to /gcp/creds.json in container env.
        """
        paths = self._patch_paths(mc_exists=True, adc_exists=True)
        mock_mc_path.return_value = paths['mc']
        mock_ocm_path.return_value = paths['ocm']
        mock_claude_path.return_value = paths['claude']
        mock_adc_path.return_value = paths['adc']

        manager, podman = self._make_manager_with_paths()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        env = call_kwargs["environment"]

        adc_host_path = "/home/user/.config/gcloud/application_default_credentials.json"
        assert adc_host_path in volumes, (
            f"ADC credentials file not mounted. Volumes: {volumes}"
        )
        assert volumes[adc_host_path]["bind"] == "/gcp/creds.json"
        assert volumes[adc_host_path]["mode"] == "ro"
        assert env.get("GOOGLE_APPLICATION_CREDENTIALS") == "/gcp/creds.json", (
            f"GOOGLE_APPLICATION_CREDENTIALS not set in container env. Got: {env}"
        )

    @pytest.mark.backwards_compatibility
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_adc_file_not_mounted_when_absent(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path, mock_adc_path
    ):
        """ADC credentials file is not in volumes when it does not exist on host."""
        paths = self._patch_paths(mc_exists=True, adc_exists=False)
        mock_mc_path.return_value = paths['mc']
        mock_ocm_path.return_value = paths['ocm']
        mock_claude_path.return_value = paths['claude']
        mock_adc_path.return_value = paths['adc']

        manager, podman = self._make_manager_with_paths()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        env = call_kwargs["environment"]

        adc_host_path = "/home/user/.config/gcloud/application_default_credentials.json"
        assert adc_host_path not in volumes, (
            f"ADC file should not be mounted when absent. Volumes: {volumes}"
        )
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in env, (
            f"GOOGLE_APPLICATION_CREDENTIALS should not be set when ADC absent. Got: {env}"
        )


class TestClaudeJsonRwMount:
    """Tests for ~/.claude.json read-write mount (MC-108 regression guard).

    Claude Code writes trust-prompt acceptance and onboarding state back to
    ~/.claude.json at runtime.  When the file is mounted read-only the write
    fails silently and Claude Code exits, forcing re-onboarding on every
    container launch.
    """

    @patch('mc.container.manager.get_claude_global_config_path')
    @patch('mc.container.manager.get_gcloud_adc_path')
    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_claude_json_mounted_readwrite_when_present(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path,
        mock_adc_path, mock_claude_json_path
    ):
        """~/.claude.json must be mounted rw so Claude Code can persist trust acceptance.

        MC-108: ~/.claude.json was previously mounted ro, causing Claude Code to
        silently exit because it could not write hasTrustDialogAccepted back to
        the file.
        """
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = False
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        mock_claude_path.return_value = claude_dir

        adc = MagicMock()
        adc.exists.return_value = False
        mock_adc_path.return_value = adc

        claude_json = MagicMock()
        claude_json.exists.return_value = True
        claude_json.__str__ = lambda self: "/home/user/.claude.json"
        mock_claude_json_path.return_value = claude_json

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/home/user/.claude.json" in volumes, (
            f"~/.claude.json is not volume-mounted. "
            f"Volumes: {list(volumes.keys())}"
        )
        assert volumes["/home/user/.claude.json"]["bind"] == "/home/mcuser/.claude.json", (
            f"claude.json mount bind target is wrong. "
            f"Got: {volumes['/home/user/.claude.json']['bind']}"
        )
        assert volumes["/home/user/.claude.json"]["mode"] == "rw", (
            f"claude.json mount must be rw for trust-prompt persistence (MC-108). "
            f"Got: {volumes['/home/user/.claude.json']['mode']}"
        )


class TestOcmConfigMountMode:
    """Tests for OCM config (ocm.json) mount mode (MC-79 regression guard).

    OCM CLI writes token refreshes back to ocm.json. If the file is mounted
    read-only, OCM commands fail with 'read-only file system' errors.
    """

    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_ocm_config_mounted_readwrite_when_present(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path
    ):
        """ocm.json must be mounted rw so OCM CLI can persist token refreshes.

        MC-79: OCM config was previously mounted ro, causing 'read-only file
        system' errors when OCM CLI tried to write back refreshed tokens.
        """
        mc_config = MagicMock()
        mc_config.exists.return_value = True
        mc_config.__str__ = lambda self: "/home/user/mc/config"
        mock_mc_path.return_value = mc_config

        ocm_config = MagicMock()
        ocm_config.exists.return_value = True
        ocm_config.__str__ = lambda self: "/home/user/.config/ocm/ocm.json"
        mock_ocm_path.return_value = ocm_config

        claude_dir = MagicMock()
        claude_dir.exists.return_value = False
        mock_claude_path.return_value = claude_dir

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/home/user/.config/ocm/ocm.json" in volumes, (
            f"OCM config not volume-mounted. Volumes: {list(volumes.keys())}"
        )
        assert volumes["/home/user/.config/ocm/ocm.json"]["bind"] == (
            "/home/mcuser/.config/ocm/ocm.json"
        ), (
            f"OCM config mount bind target is wrong. "
            f"Got: {volumes['/home/user/.config/ocm/ocm.json']['bind']}"
        )
        assert volumes["/home/user/.config/ocm/ocm.json"]["mode"] == "rw", (
            f"OCM config mount must be rw for token refresh writes (MC-79). "
            f"Got: {volumes['/home/user/.config/ocm/ocm.json']['mode']}"
        )
