"""File operation utilities."""

import logging
from pathlib import Path

from mc.exceptions import FileOperationError, WorkspaceError

logger = logging.getLogger(__name__)


def does_path_exist(path):
    """
    Check if a path exists.

    Args:
        path: Path to check

    Returns:
        bool: True if path exists, False otherwise
    """
    return Path(path).exists()


def create_file(file_path):
    """
    Create an empty file.

    Args:
        file_path: Path to file to create
    """
    try:
        path = Path(file_path)
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        logger.debug("Created file: %s", path)
    except PermissionError:
        raise FileOperationError(
            f"Permission denied creating file: {file_path}",
            f"Try: chmod +w {Path(file_path).parent}"
        )
    except OSError as e:
        raise FileOperationError(
            f"Failed to create file: {e}",
            "Check: Disk space and parent directory"
        )


def create_directory(dir_path):
    """
    Create a directory (and parents if needed).

    Args:
        dir_path: Path to directory to create
    """
    try:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Created directory: %s", path)
    except PermissionError:
        raise WorkspaceError(
            f"Permission denied creating directory: {dir_path}",
            f"Try: Check permissions with 'ls -ld {Path(dir_path).parent}'"
        )
    except OSError as e:
        raise WorkspaceError(
            f"Failed to create directory: {e}",
            "Check: Disk space and path length limits"
        )


def safe_read_file(file_path):
    """
    Read file with error handling.

    Args:
        file_path: Path to file to read

    Returns:
        str: File contents
    """
    try:
        return Path(file_path).read_text()
    except FileNotFoundError:
        raise FileOperationError(
            f"File not found: {file_path}",
            "Try: Check file path is correct"
        )
    except PermissionError:
        raise FileOperationError(
            f"Permission denied reading {file_path}",
            f"Try: chmod +r {file_path}"
        )
    except OSError as e:
        raise FileOperationError(f"Failed to read {file_path}: {e}")
