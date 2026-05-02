"""Traditional checksum file parser implementation (SHA256SUMS, etc.)."""

from __future__ import annotations

import re

from my_unicorn.constants import DEFAULT_HASH_TYPE, HashType
from my_unicorn.core.verification.checksum_parser.base import (
    ChecksumEntry,
    ChecksumParser,
)
from my_unicorn.logger import get_logger

logger = get_logger(__name__)

_HASH_LENGTH_MAP: dict[int, HashType] = {
    32: "md5",
    40: "sha1",
    64: "sha256",
    128: "sha512",
}
_HASH_TYPE_LENGTH_MAP: dict[HashType, int] = {
    hash_type: length for length, hash_type in _HASH_LENGTH_MAP.items()
}


def _parse_sha256sums_line(line: str) -> tuple[str, str] | None:
    """Parse a single line from a SHA256SUMS style file.

    Args:
        line: The line to parse.

    Returns:
        A tuple of (hash_value, filename) or None if invalid.
    """
    expected_parts = 2
    parts = line.split(None, 1)
    if len(parts) != expected_parts:
        return None

    hash_value = parts[0]
    filename_part = parts[1]
    filename_part = filename_part.removeprefix("*")
    filename_part = filename_part.removeprefix("./")

    return hash_value, filename_part


def _generate_variants(name: str) -> set[str]:
    """Generate filename variants by removing version numbers.

    Args:
        name: The original filename.

    Returns:
        A set of filename variants.
    """
    variants = {name}

    variants.update(
        re.sub(r"-\d+(?=-[a-z0-9_]+\.AppImage$)", "", name) for _ in (0,)
    )
    variants.add(re.sub(r"-\d+(?=\.AppImage$)", "", name))
    variants.add(re.sub(r"-\d+", "", name))

    return {variant for variant in variants if variant}


def _parse_hash_only_content(content: str, hash_type: HashType) -> str | None:
    """Parse checksum files that contain a single raw hash only.

    This is used for formats like `.sha512` files that sometimes
    contain only a hash without filename mapping.

    Rules:
    - Must contain exactly one non-empty, non-comment line
    - Must be a valid hex string
    - Must match the expected hash length for the detected hash type
    """
    lines = [
        line.strip()
        for line in content.strip().split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]

    if len(lines) != 1:
        return None

    candidate = lines[0]

    if not all(c in "0123456789abcdefABCDEF" for c in candidate):
        return None

    expected_length = _HASH_TYPE_LENGTH_MAP[hash_type]
    if len(candidate) != expected_length:
        logger.debug(
            "   Hash-only candidate length %d does not match %s length %d",
            len(candidate),
            hash_type,
            expected_length,
        )
        return None

    return candidate


def _parse_traditional_checksum_file(
    content: str, filename: str, hash_type: HashType
) -> str | None:
    """Parse a traditional checksum file (e.g., SHA256SUMS)."""

    logger.debug("   Parsing as traditional checksum file format")
    logger.debug("   Looking for: %s", filename)
    logger.debug("   Hash type: %s", hash_type)

    lines = content.strip().split("\n")
    logger.debug("   Total lines: %d", len(lines))

    target_variants = _generate_variants(filename)

    # Hash-only fallback for .sha256/.sha512 style files. The checksum
    # filename is not available here, so rely on the already-detected hash
    # type passed by the caller and validate the raw hash length strictly.
    hash_only = _parse_hash_only_content(content, hash_type)
    if hash_only:
        logger.debug("   ✅ Hash-only checksum detected (fallback mode)")
        logger.debug("   Hash: %s", hash_only)
        return hash_only

    # Standard filename-based parsing
    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parsed = _parse_sha256sums_line(line)
        if not parsed:
            continue

        hash_value, file_in_checksum = parsed

        # Validate hash_value is hex
        if not all(char in "0123456789abcdefABCDEF" for char in hash_value):
            continue

        logger.debug(
            "   Line %d: hash=%s... file=%s",
            line_num,
            hash_value[:16],
            file_in_checksum,
        )

        # direct match
        if file_in_checksum == filename or file_in_checksum.endswith(
            f"/{filename}"
        ):
            logger.debug("   ✅ Match found on line %d", line_num)
            logger.debug("   Hash: %s", hash_value)
            return hash_value

        # relaxed variant match
        file_variants = _generate_variants(file_in_checksum)
        if target_variants.intersection(file_variants):
            logger.debug(
                "   ⚠️ Relaxed match found on line %d (variants): %s",
                line_num,
                file_in_checksum,
            )
            logger.debug("   Hash: %s", hash_value)
            return hash_value

    logger.debug("   No match found for %s", filename)
    return None


def _parse_all_traditional_checksums(content: str) -> dict[str, str]:
    """Parse all filename-to-hash mappings from traditional checksum format.

    Args:
        content: The checksum file content.

    Returns:
        Dictionary mapping filenames to hash values.

    """
    hashes: dict[str, str] = {}

    for raw_line in content.strip().split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parsed = _parse_sha256sums_line(line)
        if not parsed:
            continue

        hash_value, filename = parsed

        if not all(char in "0123456789abcdefABCDEF" for char in hash_value):
            continue

        hashes[filename] = hash_value

    return hashes


class StandardChecksumParser(ChecksumParser):
    """Parser for traditional checksum files (SHA256SUMS, etc.)."""

    def parse(
        self, content: str, filename: str, hash_type: HashType | None = None
    ) -> ChecksumEntry | None:
        """Parse traditional checksum content.

        Args:
            content: The checksum content.
            filename: The filename to find.
            hash_type: Optional expected hash type.

        Returns:
            A ChecksumEntry or None.
        """
        expected_algorithm = hash_type or DEFAULT_HASH_TYPE
        hash_value = _parse_traditional_checksum_file(
            content, filename, expected_algorithm
        )
        if not hash_value:
            return None

        algorithm = hash_type or _HASH_LENGTH_MAP.get(
            len(hash_value), DEFAULT_HASH_TYPE
        )
        return ChecksumEntry(filename, hash_value, algorithm)
