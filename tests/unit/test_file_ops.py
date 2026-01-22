"""Unit tests for file operation utilities."""

from pathlib import Path
import pytest
from mc.utils.file_ops import does_path_exist, create_file, create_directory


def test_does_path_exist_file(tmp_path):
    """Test does_path_exist() returns True for existing file."""
    test_file = tmp_path / "test.txt"
    test_file.touch()

    assert does_path_exist(str(test_file)) is True


def test_does_path_exist_directory(tmp_path):
    """Test does_path_exist() returns True for existing directory."""
    test_dir = tmp_path / "testdir"
    test_dir.mkdir()

    assert does_path_exist(str(test_dir)) is True


def test_does_path_exist_nonexistent(tmp_path):
    """Test does_path_exist() returns False for non-existent path."""
    non_existent = tmp_path / "does_not_exist.txt"

    assert does_path_exist(str(non_existent)) is False


def test_create_file(tmp_path):
    """Test create_file() creates a new file."""
    new_file = tmp_path / "newfile.txt"

    create_file(str(new_file))

    # Verify file exists
    assert new_file.exists()
    # Verify file is empty
    assert new_file.stat().st_size == 0


def test_create_file_already_exists(tmp_path):
    """Test create_file() on existing file doesn't error."""
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("initial content")

    # Should not raise error
    create_file(str(existing_file))

    # File should still exist
    assert existing_file.exists()


def test_create_directory(tmp_path):
    """Test create_directory() creates a new directory."""
    new_dir = tmp_path / "newdir"

    create_directory(str(new_dir))

    # Verify directory exists and is a directory
    assert new_dir.exists()
    assert new_dir.is_dir()


def test_create_directory_nested(tmp_path):
    """Test create_directory() creates nested directories."""
    nested_path = tmp_path / "parent" / "child" / "grandchild"

    create_directory(str(nested_path))

    # Verify all levels created
    assert nested_path.exists()
    assert nested_path.is_dir()
    assert (tmp_path / "parent").is_dir()
    assert (tmp_path / "parent" / "child").is_dir()


def test_create_directory_already_exists(tmp_path):
    """Test create_directory() on existing directory doesn't error."""
    existing_dir = tmp_path / "existingdir"
    existing_dir.mkdir()

    # Should not raise error
    create_directory(str(existing_dir))

    # Directory should still exist
    assert existing_dir.exists()
    assert existing_dir.is_dir()
