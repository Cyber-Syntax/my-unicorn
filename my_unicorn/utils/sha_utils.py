#!/usr/bin/env python3
"""SHA utilities.

This module provides functions for handling SHA verification files.
"""

import logging

# Configure module logger
logger = logging.getLogger(__name__)


def is_sha_file(filename: str) -> bool:
    """Check if a file is a valid SHA file using simple rules.

    Args:
        filename: Filename to check

    Returns:
        bool: True if the file is a SHA file
    """
    name = filename.lower()

    # Check for specific SHA file extensions
    has_sha_extension = any(
        name.endswith(ext)
        for ext in (
            ".sha256",
            ".sha512",
            ".yml",
            ".yaml",
            ".sum",
            ".sha",
        )
    )

    # For .txt files, only consider them SHA files if they contain SHA keywords
    is_txt_with_sha = name.endswith(".txt") and any(
        keyword in name for keyword in ["sha", "checksum", "hash"]
    )

    # Check for other SHA indicators
    has_sha_keyword = "checksum" in name or "sha256" in name or "sha512" in name

    return has_sha_extension or is_txt_with_sha or has_sha_keyword


def detect_checksum_hash_type(checksum_file_name: str) -> str:
    """Detect hash type from SHA filename.

    Args:
        checksum_file_name: SHA filename

    Returns:
        str: Detected hash type ('sha256', 'sha512', etc.)
    """
    name_lower = checksum_file_name.lower()

    if "sha256" in name_lower:
        return "sha256"
    elif "sha512" in name_lower:
        return "sha512"
    elif name_lower.endswith((".yml", ".yaml")):
        # Default for YAML files
        return "sha512"

    # Default fallback
    return "sha256"
