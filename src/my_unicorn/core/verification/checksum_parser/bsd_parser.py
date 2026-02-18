"""BSD checksum file parser implementation."""

from __future__ import annotations

import re
from typing import cast

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    SUPPORTED_HASH_ALGORITHMS,
    HashType,
)
from my_unicorn.core.verification.checksum_parser.base import (
    ChecksumEntry,
    ChecksumParser,
)

_BSD_CHECKSUM_PATTERN = re.compile(
    r"(?P<algo>SHA\d+|MD5|sha\d+|md5)\s*\((?P<filename>.+)\)\s*=\s*(?P<hash>[A-Fa-f0-9]+)",
    re.IGNORECASE,
)


def _looks_like_bsd(content: str) -> bool:
    """Check if content looks like BSD checksum format.

    Args:
        content: The content to check.

    Returns:
        True if it resembles BSD format, False otherwise.
    """
    return any(
        "(" in line and ")" in line and "=" in line
        for line in content.splitlines()
    )


def _parse_all_bsd_checksums(content: str) -> dict[str, str]:
    """Parse all filename-to-hash mappings from BSD checksum format.

    Args:
        content: The checksum file content.

    Returns:
        Dictionary mapping filenames to hash values.

    """
    hashes: dict[str, str] = {}

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _BSD_CHECKSUM_PATTERN.match(line)
        if match:
            filename = match.group("filename")
            hash_value = match.group("hash")
            hashes[filename] = hash_value

    return hashes


class BSDChecksumParser(ChecksumParser):
    """Parser for BSD checksum format (e.g., "SHA256 (file) = hash")."""

    def parse(
        self, content: str, filename: str, _hash_type: HashType | None = None
    ) -> ChecksumEntry | None:
        """Parse BSD checksum content.

        Args:
            content: The BSD checksum content.
            filename: The filename to find.
            _hash_type: Unused for BSD parser (required by interface).

        Returns:
            A ChecksumEntry or None.
        """
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            match = _BSD_CHECKSUM_PATTERN.match(line)
            if not match:
                continue

            algo = match.group("algo").lower()
            file_in_checksum = match.group("filename")
            if file_in_checksum != filename:
                continue

            hash_value = match.group("hash")
            algorithm: HashType = (
                cast("HashType", algo)
                if algo in SUPPORTED_HASH_ALGORITHMS
                else DEFAULT_HASH_TYPE
            )
            return ChecksumEntry(filename, hash_value, algorithm)

        return None
