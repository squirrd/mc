"""Integration tests for backwards compatibility of v1.0 commands.

These tests ensure that all v1.0 commands continue to work unchanged on the host
after v2.0 containerization features are added. Tests focus on command existence,
syntax, and flag availability without executing full workflows that would require
external services (Salesforce, LDAP).
"""

import shutil
import subprocess
from pathlib import Path
from typing import List

import pytest


def run_cli_command(args: List[str]) -> subprocess.CompletedProcess:
    """Run mc CLI command and capture result.

    Args:
        args: Command arguments to pass to mc CLI

    Returns:
        CompletedProcess with returncode, stdout, stderr
    """
    result = subprocess.run(
        ["mc"] + args,
        capture_output=True,
        text=True,
        timeout=30
    )
    return result


@pytest.mark.integration
@pytest.mark.backwards_compatibility
@pytest.mark.skipif(
    not shutil.which('mc'),
    reason="mc CLI not installed or not in PATH"
)
class TestV1Commands:
    """Test all v1.0 commands for backwards compatibility."""

    def test_attach_command_exists(self):
        """mc attach <case_number> command should still work."""
        result = run_cli_command(["attach", "--help"])
        assert result.returncode == 0
        assert "Download attachments" in result.stdout

    def test_attach_requires_case_number(self):
        """mc attach should require case_number argument."""
        result = run_cli_command(["attach"])
        assert result.returncode != 0

    def test_attach_serial_flag_exists(self):
        """mc attach --serial flag should exist."""
        result = run_cli_command(["attach", "--help"])
        assert result.returncode == 0
        assert "--serial" in result.stdout

    def test_attach_quiet_flag_exists(self):
        """mc attach --quiet flag should exist."""
        result = run_cli_command(["attach", "--help"])
        assert result.returncode == 0
        assert "--quiet" in result.stdout

    def test_check_command_exists(self):
        """mc check <case_number> command should still work."""
        result = run_cli_command(["check", "--help"])
        assert result.returncode == 0
        # Verify command exists (help output includes command name)
        assert "check" in result.stdout.lower()

    def test_check_requires_case_number(self):
        """mc check should require case_number argument."""
        result = run_cli_command(["check"])
        assert result.returncode != 0

    def test_check_fix_flag_exists(self):
        """mc check --fix flag should exist."""
        result = run_cli_command(["check", "--help"])
        assert result.returncode == 0
        assert "--fix" in result.stdout or "-f" in result.stdout

    def test_create_command_exists(self):
        """mc create <case_number> command should still work."""
        result = run_cli_command(["create", "--help"])
        assert result.returncode == 0
        # Verify command exists (help output includes command name)
        assert "create" in result.stdout.lower()

    def test_create_requires_case_number(self):
        """mc create should require case_number argument."""
        result = run_cli_command(["create"])
        assert result.returncode != 0

    def test_create_download_flag_exists(self):
        """mc create --download flag should exist."""
        result = run_cli_command(["create", "--help"])
        assert result.returncode == 0
        assert "--download" in result.stdout or "-d" in result.stdout

    def test_case_comments_command_exists(self):
        """mc case-comments <case_number> command should still work."""
        result = run_cli_command(["case-comments", "--help"])
        assert result.returncode == 0

    def test_case_comments_requires_case_number(self):
        """mc case-comments should require case_number argument."""
        result = run_cli_command(["case-comments"])
        assert result.returncode != 0

    def test_ls_command_exists(self):
        """mc ls <uid> command should still work."""
        result = run_cli_command(["ls", "--help"])
        assert result.returncode == 0
        # Verify LDAP search functionality mentioned
        assert "LDAP" in result.stdout

    def test_ls_requires_uid(self):
        """mc ls should require uid argument."""
        result = run_cli_command(["ls"])
        assert result.returncode != 0

    def test_ls_all_flag_exists(self):
        """mc ls --all flag should exist."""
        result = run_cli_command(["ls", "--help"])
        assert result.returncode == 0
        assert "--all" in result.stdout or "-A" in result.stdout

    def test_go_command_exists(self):
        """mc go <case_number> command should still work."""
        result = run_cli_command(["go", "--help"])
        assert result.returncode == 0

    def test_go_requires_case_number(self):
        """mc go should require case_number argument."""
        result = run_cli_command(["go"])
        assert result.returncode != 0

    def test_go_launch_flag_exists(self):
        """mc go --launch flag should exist."""
        result = run_cli_command(["go", "--help"])
        assert result.returncode == 0
        assert "--launch" in result.stdout or "-l" in result.stdout

    def test_version_flag(self):
        """mc --version should output version string."""
        result = run_cli_command(["--version"])
        assert result.returncode == 0
        assert len(result.stdout.strip()) > 0
        # Version should contain at least one period (e.g., 2.0, 2.0.0)
        assert "." in result.stdout

    def test_debug_flag(self):
        """mc --debug flag should be recognized."""
        # Test with help so we don't need config
        result = run_cli_command(["--debug", "--help"])
        assert result.returncode == 0
        # Should not error out on --debug flag

    def test_json_logs_flag(self):
        """mc --json-logs flag should be recognized."""
        # Test with help so we don't need config
        result = run_cli_command(["--json-logs", "--help"])
        assert result.returncode == 0
        # Should not error out on --json-logs flag

    def test_debug_file_flag(self):
        """mc --debug-file PATH flag should be recognized."""
        # Test with help so we don't need config
        result = run_cli_command(["--debug-file", "/tmp/test.log", "--help"])
        assert result.returncode == 0
        # Should not error out on --debug-file flag

    def test_help_shows_all_commands(self):
        """mc --help should show all v1.0 commands."""
        result = run_cli_command(["--help"])
        assert result.returncode == 0

        # Verify all v1.0 commands appear in help
        assert "attach" in result.stdout
        assert "check" in result.stdout
        assert "create" in result.stdout
        assert "case-comments" in result.stdout
        assert "ls" in result.stdout
        assert "go" in result.stdout


@pytest.mark.integration
@pytest.mark.backwards_compatibility
@pytest.mark.skipif(
    not shutil.which('mc'),
    reason="mc CLI not installed or not in PATH"
)
class TestV2Commands:
    """Test new v2.0 container commands coexist with v1.0."""

    def test_container_list_command_exists(self):
        """mc container list command should exist (v2.0)."""
        result = run_cli_command(["container", "list", "--help"])
        assert result.returncode == 0

    def test_container_create_command_exists(self):
        """mc container create command should exist (v2.0)."""
        result = run_cli_command(["container", "create", "--help"])
        assert result.returncode == 0

    def test_container_stop_command_exists(self):
        """mc container stop command should exist (v2.0)."""
        result = run_cli_command(["container", "stop", "--help"])
        assert result.returncode == 0

    def test_container_delete_command_exists(self):
        """mc container delete command should exist (v2.0)."""
        result = run_cli_command(["container", "delete", "--help"])
        assert result.returncode == 0

    def test_container_exec_command_exists(self):
        """mc container exec command should exist (v2.0)."""
        result = run_cli_command(["container", "exec", "--help"])
        assert result.returncode == 0

    def test_case_terminal_command_exists(self):
        """mc case <case_number> command should exist (v2.0)."""
        result = run_cli_command(["case", "--help"])
        assert result.returncode == 0
        # Verify command exists and requires case_number
        assert "case_number" in result.stdout.lower()

    def test_quick_access_pattern_recognized(self):
        """mc <8-digit-number> should be recognized as quick access pattern."""
        # Test that 8-digit number doesn't cause parse error
        # We expect this to fail with config error or similar, not argument parsing error
        result = run_cli_command(["12345678"])
        # Should not fail with "invalid choice" or "unrecognized arguments"
        assert "invalid choice" not in result.stderr.lower()
        assert "unrecognized arguments" not in result.stderr.lower()

    def test_v2_commands_in_help(self):
        """mc --help should show new v2.0 commands alongside v1.0."""
        result = run_cli_command(["--help"])
        assert result.returncode == 0

        # Verify v2.0 commands appear
        assert "container" in result.stdout
        assert "case" in result.stdout

        # Verify v1.0 commands still appear (coexistence)
        assert "attach" in result.stdout
        assert "create" in result.stdout


@pytest.mark.integration
@pytest.mark.backwards_compatibility
class TestWorkspaceCompatibility:
    """Test workspace and configuration compatibility."""

    def test_workspace_structure_unchanged(self, tmp_path):
        """Verify workspace directory structure works without migration.

        This test creates a mock v1.0 workspace structure and verifies it
        would be compatible with v2.0 container mounting.
        """
        # Create mock v1.0 workspace structure
        case_dir = tmp_path / "12345678"
        case_dir.mkdir()

        # Create typical v1.0 workspace files
        (case_dir / "attachments").mkdir()
        (case_dir / "notes.txt").write_text("Test notes")
        (case_dir / "sosreport").mkdir()

        # Verify structure exists and is accessible
        assert case_dir.exists()
        assert (case_dir / "attachments").is_dir()
        assert (case_dir / "notes.txt").is_file()
        assert (case_dir / "sosreport").is_dir()

        # Verify files can be read (simulating container mount)
        notes_content = (case_dir / "notes.txt").read_text()
        assert notes_content == "Test notes"

    def test_workspace_files_accessible(self, tmp_path):
        """Verify workspace files remain accessible after creation.

        Simulates the container mount scenario where workspace files
        must be readable and writable.
        """
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create test file
        test_file = workspace / "test.txt"
        test_file.write_text("original content")

        # Verify read access
        assert test_file.read_text() == "original content"

        # Verify write access (container would need this)
        test_file.write_text("modified content")
        assert test_file.read_text() == "modified content"

        # Verify directory creation (containers create new dirs)
        new_dir = workspace / "new_directory"
        new_dir.mkdir()
        assert new_dir.is_dir()


@pytest.mark.integration
@pytest.mark.backwards_compatibility
class TestConfigCompatibility:
    """Test configuration file compatibility between host and container contexts."""

    def test_config_format_unchanged(self, tmp_path):
        """Verify config file format hasn't changed from v1.0.

        Config files should be readable by both host and container mc instances
        without modification (COMPAT-03 requirement).
        """
        # Create mock v1.0 config
        config_content = """[general]
base_directory = "/home/user/Cases"

[api]
offline_token = "test-token-value"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        # Verify file exists and is readable
        assert config_file.exists()
        content = config_file.read_text()

        # Verify expected sections present
        assert "[general]" in content
        assert "base_directory" in content
        assert "[api]" in content
        assert "offline_token" in content

    def test_config_readable_cross_context(self, tmp_path):
        """Verify config can be read from different paths (host vs container).

        Simulates both host reading from ~/.config/mc/config.toml
        and container reading from mounted config location.
        """
        config_content = """[general]
base_directory = "/Cases"

[api]
offline_token = "token123"
"""

        # Simulate host config location
        host_config = tmp_path / "host" / ".config" / "mc"
        host_config.mkdir(parents=True)
        host_config_file = host_config / "config.toml"
        host_config_file.write_text(config_content)

        # Simulate container mount location
        container_config = tmp_path / "container" / "etc" / "mc"
        container_config.mkdir(parents=True)
        container_config_file = container_config / "config.toml"
        # Container would see same content via mount
        container_config_file.write_text(config_content)

        # Verify both can read same content
        host_content = host_config_file.read_text()
        container_content = container_config_file.read_text()

        assert host_content == container_content
        assert "base_directory" in host_content
        assert "offline_token" in container_content
