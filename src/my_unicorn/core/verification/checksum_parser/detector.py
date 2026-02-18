"""Checksum format detection and entry finding utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from my_unicorn.core.verification.checksum_parser.bsd_parser import (
    BSDChecksumParser,
    _looks_like_bsd,
    _parse_all_bsd_checksums,
)
from my_unicorn.core.verification.checksum_parser.traditional_parser import (
    StandardChecksumParser,
    _parse_all_traditional_checksums,
)
from my_unicorn.core.verification.checksum_parser.yaml_parser import (
    YAMLChecksumParser,
    _is_yaml_content,
    _parse_all_yaml_checksums,
)
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from my_unicorn.constants import HashType
    from my_unicorn.core.verification.checksum_parser.base import (
        ChecksumEntry,
        ChecksumParser,
    )


logger = get_logger(__name__)


def find_checksum_entry(
    content: str, filename: str, hash_type: HashType | None = None
) -> ChecksumEntry | None:
    """Find and parse a checksum entry from content.

    Args:
        content: The checksum file content.
        filename: The filename to find.
        hash_type: Optional expected hash type.

    Returns:
        A ChecksumEntry or None if not found.
    """
    parser: ChecksumParser
    if _is_yaml_content(content):
        parser = YAMLChecksumParser()
    elif _looks_like_bsd(content):
        parser = BSDChecksumParser()
    else:
        parser = StandardChecksumParser()

    return parser.parse(content, filename, hash_type)


def parse_checksum_file(
    content: str, filename: str, hash_type: HashType
) -> str | None:
    """Parse checksum file and return the hash value.

    Args:
        content: The checksum file content.
        filename: The filename to find.
        hash_type: The expected hash type.

    Returns:
        The hash value as string or None.
    """
    entry = find_checksum_entry(content, filename, hash_type)
    return entry.hash_value if entry else None


def detect_hash_type_from_checksum_filename(
    filename: str,
) -> HashType | None:
    """Detect hash type from checksum filename.

    Args:
        filename: The checksum filename.

    Returns:
        The detected hash type or None.
    """
    filename_lower = filename.lower()

    hash_patterns: dict[HashType, Iterable[str]] = {
        "sha512": ["sha512", "sha-512"],
        "sha256": ["sha256", "sha-256"],
        "sha1": ["sha1", "sha-1"],
        "md5": ["md5"],
    }

    for hash_type, patterns in hash_patterns.items():
        if any(pattern in filename_lower for pattern in patterns):
            logger.debug("   Detected %s hash type from filename", hash_type)
            return hash_type

    if filename_lower.endswith((".yml", ".yaml")):
        return "sha256"

    return None


def parse_all_checksums(content: str) -> dict[str, str]:
    """Parse all filename-to-hash mappings from a checksum file.

    Automatically detects the checksum file format (YAML, BSD, or traditional)
    and parses all entries.

    Args:
        content: The checksum file content.

    Returns:
        Dictionary mapping filenames to hash values.

    """
    if _is_yaml_content(content):
        return _parse_all_yaml_checksums(content)
    if _looks_like_bsd(content):
        return _parse_all_bsd_checksums(content)
    return _parse_all_traditional_checksums(content)
