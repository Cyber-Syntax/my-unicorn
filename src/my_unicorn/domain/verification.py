"""Checksum verification business logic.

Pure logic for detecting checksum types and extracting checksums
from verification files.
"""

import re

from my_unicorn.domain.types import ChecksumType


def detect_checksum_type(content: str) -> ChecksumType:
    """Detect checksum type from file content.

    Args:
        content: Content of checksum file

    Returns:
        Detected checksum type
    """
    content_lower = content.lower()

    # Check for SHA-512 (128 hex characters)
    if re.search(r"\b[a-f0-9]{128}\b", content_lower):
        return ChecksumType.SHA512

    # Check for SHA-256 (64 hex characters)
    if re.search(r"\b[a-f0-9]{64}\b", content_lower):
        return ChecksumType.SHA256

    # Check for explicit algorithm markers
    if "sha512" in content_lower or "sha-512" in content_lower:
        return ChecksumType.SHA512

    if "sha256" in content_lower or "sha-256" in content_lower:
        return ChecksumType.SHA256

    return ChecksumType.UNKNOWN


def extract_checksum(
    content: str, filename: str, checksum_type: ChecksumType
) -> str | None:
    """Extract checksum for specific file from checksum file content.

    Args:
        content: Content of checksum file
        filename: Target filename to find checksum for
        checksum_type: Type of checksum to extract

    Returns:
        Checksum string or None if not found
    """
    if checksum_type == ChecksumType.UNKNOWN:
        return None

    # Determine expected hash length
    expected_length = 64 if checksum_type == ChecksumType.SHA256 else 128

    # Try different checksum file formats
    checksum = _extract_from_standard_format(
        content, filename, expected_length
    )
    if checksum:
        return checksum

    checksum = _extract_from_bsd_format(content, filename, expected_length)
    if checksum:
        return checksum

    # Fallback: if content is just a hash, return it
    if len(content.strip()) == expected_length and re.match(
        r"^[a-fA-F0-9]+$", content.strip()
    ):
        return content.strip().lower()

    return None


def _extract_from_standard_format(
    content: str, filename: str, hash_length: int
) -> str | None:
    """Extract checksum from standard format: 'hash filename'.

    Args:
        content: Checksum file content
        filename: Target filename
        hash_length: Expected hash length

    Returns:
        Checksum or None
    """
    # Pattern: <hash> <optional asterisk> <filename>
    pattern = rf"([a-fA-F0-9]{{{hash_length}}})\s+\*?{re.escape(filename)}"

    match = re.search(pattern, content)
    if match:
        return match.group(1).lower()

    return None


def _extract_from_bsd_format(
    content: str, filename: str, hash_length: int
) -> str | None:
    """Extract checksum from BSD format: 'ALGO (filename) = hash'.

    Args:
        content: Checksum file content
        filename: Target filename
        hash_length: Expected hash length

    Returns:
        Checksum or None
    """
    # Pattern: SHA256 (filename) = hash
    pattern = (
        rf"SHA(?:256|512)\s*\({re.escape(filename)}\)\s*="
        rf"\s*([a-fA-F0-9]{{{hash_length}}})"
    )

    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    return None


def is_checksum_valid(checksum: str, checksum_type: ChecksumType) -> bool:
    """Validate checksum format.

    Args:
        checksum: Checksum string to validate
        checksum_type: Expected checksum type

    Returns:
        True if valid format, False otherwise
    """
    if checksum_type == ChecksumType.SHA256:
        return len(checksum) == 64 and re.match(r"^[a-f0-9]{64}$", checksum)

    if checksum_type == ChecksumType.SHA512:
        return len(checksum) == 128 and re.match(r"^[a-f0-9]{128}$", checksum)

    return False
