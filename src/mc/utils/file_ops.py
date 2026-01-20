"""File operation utilities."""

import os


def does_path_exist(path):
    """
    Check if a path exists.

    Args:
        path: Path to check

    Returns:
        bool: True if path exists, False otherwise
    """
    return os.path.exists(path)


def create_file(file_path):
    """
    Create an empty file.

    Args:
        file_path: Path to file to create
    """
    open(file_path, 'a').close()


def create_directory(dir_path):
    """
    Create a directory (and parents if needed).

    Args:
        dir_path: Path to directory to create
    """
    os.makedirs(dir_path, exist_ok=True)
