#!/usr/bin/env python3
"""SHA hash calculation utilities for test framework.

This module provides pure hash calculation functions to eliminate
code duplication and ensure consistent hash verification.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import hashlib
from pathlib import Path


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of file.

    Uses chunked reading (8KB chunks) for memory efficiency with large files.

    Args:
        file_path: Path to file

    Returns:
        Lowercase hexadecimal SHA256 hash string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    sha256_hash = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def calculate_sha512(file_path: Path) -> str:
    """Calculate SHA512 hash of file.

    Uses chunked reading (8KB chunks) for memory efficiency with large files.

    Args:
        file_path: Path to file

    Returns:
        Lowercase hexadecimal SHA512 hash string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    sha512_hash = hashlib.sha512()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha512_hash.update(chunk)
    return sha512_hash.hexdigest()


def verify_hash(
    file_path: Path, expected: str, algorithm: str = "sha256"
) -> bool:
    """Verify file hash matches expected value.

    Case-insensitive comparison for hash strings.

    Args:
        file_path: Path to file
        expected: Expected hash value
        algorithm: Hash algorithm ("sha256" or "sha512")

    Returns:
        True if hash matches, False otherwise

    Raises:
        ValueError: If algorithm is not supported
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    algorithm = algorithm.lower()
    if algorithm == "sha256":
        actual = calculate_sha256(file_path)
    elif algorithm == "sha512":
        actual = calculate_sha512(file_path)
    else:
        msg = f"Unsupported hash algorithm: {algorithm}"
        raise ValueError(msg)

    return actual.lower() == expected.lower()


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """Calculate hash of string.

    Args:
        text: String to hash
        algorithm: Hash algorithm ("sha256" or "sha512")

    Returns:
        Lowercase hexadecimal hash string

    Raises:
        ValueError: If algorithm is not supported
    """
    algorithm = algorithm.lower()
    if algorithm == "sha256":
        return hashlib.sha256(text.encode()).hexdigest()
    if algorithm == "sha512":
        return hashlib.sha512(text.encode()).hexdigest()
    msg = f"Unsupported hash algorithm: {algorithm}"
    raise ValueError(msg)
