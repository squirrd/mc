"""Unit tests for terminal shell customization and banner generation."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mc.terminal.banner import format_field, generate_banner
from mc.terminal.shell import generate_bashrc, get_bashrc_path, write_bashrc


class TestGenerateBashrc:
    """Tests for generate_bashrc function."""

    def test_generate_bashrc_prompt(self):
        """Verify PS1 contains [MC-{case_number}]."""
        case_number = "12345678"
        metadata = {"case_number": case_number}
        
        bashrc = generate_bashrc(case_number, metadata)
        
        assert f"export PS1='[MC-{case_number}]" in bashrc

    def test_generate_bashrc_aliases(self):
        """Verify ll and case-info aliases present."""
        metadata = {"case_number": "12345678"}
        
        bashrc = generate_bashrc("12345678", metadata)
        
        assert "alias ll='ls -lah'" in bashrc
        assert "alias case-info='echo \"Case: ${MC_CASE_ID}\"'" in bashrc

    def test_generate_bashrc_help_function(self):
        """Verify mc-help function defined."""
        metadata = {"case_number": "12345678"}
        
        bashrc = generate_bashrc("12345678", metadata)
        
        assert "mc-help()" in bashrc
        assert "MC Container Environment" in bashrc

    def test_generate_bashrc_env_vars(self):
        """Verify MC_CASE_ID, MC_CUSTOMER, MC_DESCRIPTION exported."""
        case_number = "12345678"
        metadata = {
            "case_number": case_number,
            "customer_name": "Test Corp",
            "description": "Test description",
        }
        
        bashrc = generate_bashrc(case_number, metadata)
        
        assert f"export MC_CASE_ID='{case_number}'" in bashrc
        assert "export MC_CUSTOMER='Test Corp'" in bashrc
        assert "export MC_DESCRIPTION='Test description'" in bashrc

    def test_generate_bashrc_env_vars_defaults(self):
        """Verify environment variables have defaults for missing metadata."""
        metadata = {"case_number": "12345678"}
        
        bashrc = generate_bashrc("12345678", metadata)
        
        assert "export MC_CUSTOMER='Unknown'" in bashrc
        assert "export MC_DESCRIPTION=''" in bashrc

    def test_generate_bashrc_banner_call(self):
        """Verify generate_banner() output included in bashrc."""
        metadata = {
            "case_number": "12345678",
            "customer_name": "Test Corp",
            "description": "Test issue",
        }
        
        bashrc = generate_bashrc("12345678", metadata)
        
        # Should contain banner delimiters
        assert "cat << 'BANNER_EOF'" in bashrc
        assert "BANNER_EOF" in bashrc
        # Should contain banner content
        assert "Case: 12345678" in bashrc
        assert "Customer: Test Corp" in bashrc


class TestGetBashrcPath:
    """Tests for get_bashrc_path function."""

    def test_get_bashrc_path_format(self):
        """Verify path format matches expected pattern."""
        case_number = "12345678"
        
        path = get_bashrc_path(case_number)
        
        # Should end with /bashrc/mc-{case_number}.bashrc
        assert path.endswith(f"/bashrc/mc-{case_number}.bashrc")
        assert "mc-12345678.bashrc" in path

    def test_get_bashrc_path_expansion(self):
        """Verify path is absolute (no ~ expansion needed)."""
        path = get_bashrc_path("12345678")
        
        # Should be absolute path
        assert os.path.isabs(path)
        assert not path.startswith("~")

    @patch("mc.terminal.shell.user_data_dir")
    def test_get_bashrc_path_uses_platformdirs(self, mock_user_data_dir):
        """Verify platformdirs.user_data_dir is used."""
        mock_user_data_dir.return_value = "/tmp/mc-test"
        
        path = get_bashrc_path("12345678")
        
        mock_user_data_dir.assert_called_once_with("mc", "redhat")
        assert "/tmp/mc-test/bashrc/mc-12345678.bashrc" == path

    @patch("mc.terminal.shell.Path.mkdir")
    @patch("mc.terminal.shell.user_data_dir")
    def test_get_bashrc_path_creates_directory(self, mock_user_data_dir, mock_mkdir):
        """Verify parent directory created if missing."""
        mock_user_data_dir.return_value = "/tmp/mc-test"
        
        get_bashrc_path("12345678")
        
        # Should create bashrc directory with parents=True, exist_ok=True
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestWriteBashrc:
    """Tests for write_bashrc function."""

    def test_write_bashrc_creates_file(self):
        """Verify file created at correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_number = "12345678"
            metadata = {"case_number": case_number}
            
            with patch("mc.terminal.shell.user_data_dir", return_value=tmpdir):
                bashrc_path = write_bashrc(case_number, metadata)
            
            # File should exist
            assert os.path.exists(bashrc_path)
            assert os.path.isfile(bashrc_path)

    def test_write_bashrc_content(self):
        """Verify file content matches generated bashrc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_number = "12345678"
            metadata = {
                "case_number": case_number,
                "customer_name": "Test Corp",
            }
            
            with patch("mc.terminal.shell.user_data_dir", return_value=tmpdir):
                bashrc_path = write_bashrc(case_number, metadata)
            
            # Read file content
            with open(bashrc_path, "r") as f:
                content = f.read()
            
            # Should match generated bashrc
            expected = generate_bashrc(case_number, metadata)
            assert content == expected

    def test_write_bashrc_returns_absolute_path(self):
        """Verify absolute path returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = {"case_number": "12345678"}
            
            with patch("mc.terminal.shell.user_data_dir", return_value=tmpdir):
                bashrc_path = write_bashrc("12345678", metadata)
            
            assert os.path.isabs(bashrc_path)

    def test_write_bashrc_file_permissions(self):
        """Verify file has 0o644 permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = {"case_number": "12345678"}
            
            with patch("mc.terminal.shell.user_data_dir", return_value=tmpdir):
                bashrc_path = write_bashrc("12345678", metadata)
            
            # Check file permissions
            stat_info = os.stat(bashrc_path)
            permissions = stat_info.st_mode & 0o777
            assert permissions == 0o644


class TestGenerateBanner:
    """Tests for generate_banner function."""

    def test_generate_banner_full_metadata(self):
        """Verify all fields formatted correctly."""
        metadata = {
            "case_number": "12345678",
            "customer_name": "Test Corp",
            "description": "Test description",
            "summary": "Test summary",
            "next_steps": "Test next steps",
        }
        
        banner = generate_banner(metadata)
        
        assert "Case: 12345678" in banner
        assert "Customer: Test Corp" in banner
        assert "Description: Test description" in banner
        assert "Summary:" in banner
        assert "Test summary" in banner
        assert "Next Steps:" in banner
        assert "Test next steps" in banner
        assert "=================================================" in banner

    def test_generate_banner_missing_fields(self):
        """Verify graceful handling of None values."""
        metadata = {
            "case_number": "12345678",
            # All optional fields missing
        }
        
        banner = generate_banner(metadata)
        
        # Should not crash, should show N/A for missing fields
        assert "Case: 12345678" in banner
        assert "Customer: N/A" in banner
        assert "Description: N/A" in banner

    def test_generate_banner_no_comments(self):
        """Verify comments field NOT included in banner."""
        metadata = {
            "case_number": "12345678",
            "customer_name": "Test Corp",
            "description": "Test description",
            "comments": "This is a secret comment",  # Should NOT appear
        }
        
        banner = generate_banner(metadata)
        
        # Comments should NOT be in banner
        assert "comments" not in banner.lower()
        assert "secret comment" not in banner

    def test_generate_banner_wrapping(self):
        """Verify long descriptions wrapped to 80 chars."""
        long_description = "A" * 100  # 100 characters
        metadata = {
            "case_number": "12345678",
            "description": long_description,
        }
        
        banner = generate_banner(metadata)
        
        # Each line should be <= 80 characters (excluding banner delimiters)
        lines = banner.split("\n")
        for line in lines:
            if not line.startswith("="):  # Ignore delimiter lines
                assert len(line) <= 80

    def test_generate_banner_empty_summary_omitted(self):
        """Verify empty summary section not included."""
        metadata = {
            "case_number": "12345678",
            "customer_name": "Test Corp",
            "description": "Test description",
            "summary": "",  # Empty summary
        }
        
        banner = generate_banner(metadata)
        
        # Summary section should not appear for empty string
        lines = banner.split("\n")
        assert "Summary:" not in lines

    def test_generate_banner_empty_next_steps_omitted(self):
        """Verify empty next steps section not included."""
        metadata = {
            "case_number": "12345678",
            "customer_name": "Test Corp",
            "description": "Test description",
            "next_steps": "   ",  # Whitespace only
        }
        
        banner = generate_banner(metadata)
        
        # Next steps section should not appear for whitespace-only
        lines = banner.split("\n")
        assert "Next Steps:" not in lines


class TestFormatField:
    """Tests for format_field function."""

    def test_format_field_none(self):
        """Verify None values return 'N/A'."""
        result = format_field(None)
        assert result == "N/A"

    def test_format_field_empty_string(self):
        """Verify empty strings return 'N/A'."""
        result = format_field("")
        assert result == "N/A"

    def test_format_field_whitespace_only(self):
        """Verify whitespace-only strings return 'N/A'."""
        result = format_field("   ")
        assert result == "N/A"

    def test_format_field_wrapping(self):
        """Verify text wrapped to specified width."""
        long_text = "A" * 100
        
        result = format_field(long_text, max_width=50)
        
        # Should be wrapped to 50 chars per line
        lines = result.split("\n")
        for line in lines:
            assert len(line) <= 50

    def test_format_field_default_width(self):
        """Verify default width is 80."""
        long_text = "A" * 100
        
        result = format_field(long_text)
        
        # First line should be 80 chars (default)
        lines = result.split("\n")
        assert len(lines[0]) == 80
