"""Checksum extraction utilities for release descriptions.

This module provides utility functions for extracting checksums from release description text.
It focuses on pure parsing functionality without API calls or verification logic.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_checksums_from_text(
    description_text: str, target_filename: str | None = None
) -> list[str]:
    """Extract checksum lines from release description text.

    Args:
        description_text: Release description text to parse
        target_filename: Optional filename to filter checksums for

    Returns:
        List of checksum lines in "hash filename" format

    Raises:
        ValueError: If no checksums found in the text
    """
    if not description_text:
        raise ValueError("No description text provided")

    # Import parser here to avoid circular imports
    from src.utils.checksums.parser import parse_checksums_from_description

    checksums = parse_checksums_from_description(description_text)

    if not checksums:
        raise ValueError("No checksums found in description text")

    logger.debug(f"Found {len(checksums)} checksums in description text")

    # Filter checksums for specific target file if provided
    if target_filename and checksums:
        filename_lower = Path(target_filename).name.lower()
        filtered = [line for line in checksums if filename_lower in line.lower()]

        if filtered:
            logger.debug(f"Filtered to {len(filtered)} checksums for {target_filename}")
            return filtered
        else:
            logger.warning(f"No checksums found for {target_filename}, returning all")

    return checksums


def filter_checksums_by_filename(checksums: list[str], target_filename: str) -> list[str]:
    """Filter checksums for a specific target filename.

    Args:
        checksums: List of checksum lines
        target_filename: Target filename to filter for

    Returns:
        Filtered list of checksum lines matching the target filename
    """
    if not target_filename:
        return checksums

    filename_lower = Path(target_filename).name.lower()
    filtered = [line for line in checksums if filename_lower in line.lower()]

    logger.debug(f"Filtered {len(checksums)} checksums to {len(filtered)} for {target_filename}")
    return filtered


def validate_checksum_format(checksum_line: str) -> bool:
    """Validate that a checksum line has the correct format.

    Args:
        checksum_line: Single checksum line to validate

    Returns:
        True if the line matches expected "hash filename" format
    """
    import re
    
    # Check for SHA256 hash pattern (64 hex chars) followed by filename
    return bool(re.match(r"^[0-9a-f]{64}\s+\S+", checksum_line.strip(), re.IGNORECASE))


def extract_hash_and_filename(checksum_line: str) -> tuple[str, str] | None:
    """Extract hash and filename from a checksum line.

    Args:
        checksum_line: Checksum line in "hash filename" format

    Returns:
        Tuple of (hash, filename) if valid, None if invalid format
    """
    parts = checksum_line.strip().split(maxsplit=1)
    if len(parts) >= 2 and validate_checksum_format(checksum_line):
        return parts[0].lower(), parts[1]
    return None