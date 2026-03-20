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


class TestAllMountsTogether:
    """Tests for workspace + mc/config + OCM + claude combined mount scenarios."""

    @patch('mc.container.manager.get_claude_config_path')
    @patch('mc.container.manager.get_ocm_config_path')
    @patch('mc.container.manager.get_mc_config_path')
    @patch('mc.container.manager.os.makedirs')
    def test_all_mounts_present_when_all_paths_exist(
        self, mock_makedirs, mock_mc_path, mock_ocm_path, mock_claude_path
    ):
        """Workspace, mc/config, OCM, and claude all mounted when all host paths exist."""
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

        manager, podman = _make_manager()
        manager.create("12345678", "/workspace", "Customer")

        mc_state_path = str(Path.home() / "mc" / "state")
        call_kwargs = podman.client.containers.create.call_args[1]
        volumes = call_kwargs["volumes"]
        assert "/workspace" in volumes
        assert "/home/user/mc/config" in volumes
        assert "/home/user/.config/ocm/ocm.json" in volumes
        assert "/home/user/.claude" in volumes
        assert mc_state_path in volumes
        assert len(volumes) == 5
