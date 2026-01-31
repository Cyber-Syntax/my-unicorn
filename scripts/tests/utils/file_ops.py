#!/usr/bin/env python3
"""Pure file operation utilities for test framework.

This module provides pure, reusable file system operations to eliminate
code duplication across the test framework.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import os
from pathlib import Path


def file_exists(path: Path) -> bool:
    """Check if file exists.

    Args:
        path: Path to check

    Returns:
        True if file exists, False otherwise
    """
    return path.exists()


def is_executable(path: Path) -> bool:
    """Check if file is executable.

    Args:
        path: Path to file

    Returns:
        True if file is executable, False otherwise
    """
    return path.exists() and os.access(path, os.X_OK)


def get_file_size(path: Path) -> int:
    """Get file size in bytes.

    Args:
        path: Path to file

    Returns:
        File size in bytes, 0 if file doesn't exist
    """
    return path.stat().st_size if path.exists() else 0


def read_file_text(path: Path) -> str:
    """Read text file content.

    Args:
        path: Path to text file

    Returns:
        File content as string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    return path.read_text(encoding="utf-8")


def read_file_bytes(path: Path) -> bytes:
    """Read binary file content.

    Args:
        path: Path to binary file

    Returns:
        File content as bytes

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    return path.read_bytes()


def write_file_bytes(path: Path, content: bytes) -> None:
    """Write binary content to file.

    Args:
        path: Path to file
        content: Binary content to write

    Raises:
        PermissionError: If file can't be written
    """
    path.write_bytes(content)


def write_file_text(path: Path, content: str) -> None:
    """Write text content to file.

    Args:
        path: Path to file
        content: Text content to write

    Raises:
        PermissionError: If file can't be written
    """
    path.write_text(content, encoding="utf-8")


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if needed.

    Args:
        path: Path to directory

    Raises:
        PermissionError: If directory can't be created
    """
    path.mkdir(parents=True, exist_ok=True)


def remove_file(path: Path) -> bool:
    """Remove file if it exists.

    Args:
        path: Path to file

    Returns:
        True if file was removed, False if it didn't exist

    Raises:
        PermissionError: If file can't be removed
    """
    if path.exists():
        path.unlink()
        return True
    return False


def get_file_mtime(path: Path) -> float:
    """Get file modification time.

    Args:
        path: Path to file

    Returns:
        Modification time as timestamp, 0.0 if file doesn't exist
    """
    return path.stat().st_mtime if path.exists() else 0.0
