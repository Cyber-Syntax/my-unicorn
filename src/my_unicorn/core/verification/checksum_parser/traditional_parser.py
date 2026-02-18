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


def _parse_traditional_checksum_file(
    content: str, filename: str, hash_type: HashType
) -> str | None:
    """Parse a traditional checksum file (e.g., SHA256SUMS).

    Args:
        content: The file content.
        filename: The filename to find the hash for.
        hash_type: The expected hash type.

    Returns:
        The hash value as string or None if not found.
    """
    logger.debug("   Parsing as traditional checksum file format")
    logger.debug("   Looking for: %s", filename)
    logger.debug("   Hash type: %s", hash_type)

    lines = content.strip().split("\n")
    logger.debug("   Total lines: %d", len(lines))

    target_variants = _generate_variants(filename)

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

        if file_in_checksum == filename or file_in_checksum.endswith(
            f"/{filename}"
        ):
            logger.debug("   ✅ Match found on line %d", line_num)
            logger.debug("   Hash: %s", hash_value)
            return hash_value

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
