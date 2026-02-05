"""Checksum file parsing utilities.

This module extracts checksum parsing responsibilities from :class:`Verifier`
so hash computation and parsing concerns remain separate.

The module includes encoding detection to differentiate between hexadecimal
and base64-encoded hashes, preventing corruption when normalizing hash values.
Hex detection is performed first to avoid incorrectly decoding hex hashes that
contain only valid base64 characters (e.g., "deadbeef12345678...").
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    HASH_PREFERENCE_ORDER,
    SUPPORTED_HASH_ALGORITHMS,
    YAML_DEFAULT_HASH,
    HashType,
)
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via patching in tests
    yaml = None
    _YAML_AVAILABLE = False


logger = get_logger(__name__)

_HASH_LENGTH_MAP: dict[int, HashType] = {
    32: "md5",
    40: "sha1",
    64: "sha256",
    128: "sha512",
}

_BSD_CHECKSUM_PATTERN = re.compile(
    r"(?P<algo>SHA\d+|MD5|sha\d+|md5)\s*\((?P<filename>.+)\)\s*=\s*(?P<hash>[A-Fa-f0-9]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChecksumEntry:
    """Parsed checksum entry."""

    filename: str
    hash_value: str
    algorithm: HashType


@dataclass(frozen=True)
class ChecksumFileResult:
    """Complete parsed checksum file data for caching.

    Attributes:
        source: Download URL for the checksum file.
        filename: Filename of the checksum file.
        algorithm: Hash algorithm used (SHA256, SHA512).
        hashes: Mapping of asset filename to hash value.

    """

    source: str
    filename: str
    algorithm: str
    hashes: dict[str, str]

    def to_cache_dict(self) -> dict[str, str | dict[str, str]]:
        """Convert to dictionary format for cache storage.

        Returns:
            Dictionary with source, filename, algorithm, and hashes fields.

        """
        return {
            "source": self.source,
            "filename": self.filename,
            "algorithm": self.algorithm,
            "hashes": self.hashes,
        }


class ChecksumParser:
    """Abstract base class for parsing checksum files.

    This class defines the interface for parsers that extract checksum
    information from various checksum file formats (e.g., SHA256SUMS,
    BSD checksums, YAML checksums). Concrete implementations must
    override the parse method to handle specific formats.

    The parser is responsible for finding the hash value for a given
    filename within the checksum content and returning it as a
    ChecksumEntry object.
    """

    def parse(
        self, content: str, filename: str, hash_type: HashType | None = None
    ) -> ChecksumEntry | None:
        """Parse checksum content for a specific file.

        Args:
            content: The checksum file content.
            filename: The filename to find.
            hash_type: Optional expected hash type.

        Returns:
            A ChecksumEntry or None if not found.
        """
        raise NotImplementedError


def convert_base64_to_hex(base64_hash: str) -> str:
    """Convert base64 encoded hash to hexadecimal string."""

    try:
        return base64.b64decode(base64_hash).hex()
    except Exception as exc:  # pragma: no cover - kept for safety
        logger.exception("❌ Failed to convert base64 to hex")
        msg = f"Invalid base64 hash: {base64_hash}"
        raise ValueError(msg) from exc


def _is_likely_hex(hash_value: str) -> bool:
    """Detect if a hash value is likely hexadecimal encoding.

    Checks if the hash matches common hash algorithm lengths (MD5, SHA1,
    SHA256, SHA512) and contains only valid hexadecimal characters.

    Args:
        hash_value: The hash value to check.

    Returns:
        True if the hash appears to be hexadecimal, False otherwise.

    Examples:
        >>> _is_likely_hex("abc123def4567890abcdef1234567890")  # MD5
        True
        >>> _is_likely_hex("deadbeef" * 8)  # SHA256
        True
        >>> _is_likely_hex("DEADBEEF" * 16)  # SHA512 uppercase
        True
        >>> _is_likely_hex("JNmYBTG9lqXt")  # Base64 - wrong length
        False
        >>> _is_likely_hex("ghijklmn" * 8)  # Invalid hex characters
        False
    """
    hash_value = hash_value.strip()
    hash_length = len(hash_value)

    # Check if length matches known hash algorithms
    # MD5: 32, SHA1: 40, SHA256: 64, SHA512: 128
    if hash_length not in (32, 40, 64, 128):
        return False

    # Check if all characters are valid hexadecimal
    return all(c in "0123456789abcdefABCDEF" for c in hash_value)


def _is_likely_base64(hash_value: str) -> bool:
    """Detect if a hash value is likely base64 encoding.

    Checks if the hash has valid base64 characteristics: length is multiple
    of 4, contains only valid base64 characters, and padding (=) only at end.

    Args:
        hash_value: The hash value to check.

    Returns:
        True if the hash appears to be base64-encoded, False otherwise.

    Examples:
        >>> _is_likely_base64("JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8=")
        True
        >>> _is_likely_base64("JNmYBTG9")  # Valid, no padding needed (8 chars)
        True
        >>> _is_likely_base64("abc123")  # Not multiple of 4 (6 chars)
        False
        >>> _is_likely_base64("JN=mYBTG")  # Padding in middle
        False
        >>> _is_likely_base64("")  # Empty string
        False
    """
    hash_value = hash_value.strip()
    hash_length = len(hash_value)

    # Base64 strings must be multiples of 4
    if hash_length == 0 or hash_length % 4 != 0:
        return False

    # Valid base64 alphabet (uppercase + lowercase + digits + special chars)
    base64_chars = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    )

    # Find first padding character
    padding_index = hash_value.find("=")

    # If padding exists, it must be at the end (last 2 positions)
    if padding_index != -1 and padding_index < hash_length - 2:
        return False

    # All characters must be valid base64
    return all(c in base64_chars for c in hash_value)


def _normalize_hash_value(hash_value: str) -> str:
    """Normalize a hash value to hexadecimal representation.

    Detects encoding (hex vs base64) and converts to hexadecimal.
    Handles algorithm prefixes (e.g., "sha256:abc123...").

    This function prevents corruption of hexadecimal hashes that contain only
    valid base64 characters (e.g., "deadbeef12345678..."). Without proper
    detection, such hashes would be incorrectly decoded as base64, producing
    garbage output. The fix ensures hex detection runs BEFORE base64 decode.

    The function applies the following priority:
        1. If hex → return unchanged (lowercased)
        2. If base64 → convert to hex
        3. Otherwise → return unchanged

    Args:
        hash_value: The hash value to normalize.

    Returns:
        The normalized hash value as hexadecimal string (lowercase).

    Examples:
        >>> # Hex hash preserved (not corrupted)
        >>> _normalize_hash_value("deadbeef12345678" * 4)  # SHA256
        'deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678'
        >>> # Base64 converted to hex
        >>> b64 = "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8="
        >>> _normalize_hash_value(b64)
        '24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f'
        >>> # Algorithm prefix stripped
        >>> _normalize_hash_value("sha256:deadbeef12345678" * 4)
        'deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678'
    """
    # Strip algorithm prefix (e.g., "sha256:")
    if ":" in hash_value:
        _, _, hash_value = hash_value.partition(":")

    # CRITICAL FIX: Detect hex BEFORE attempting base64 decode
    if _is_likely_hex(hash_value):
        return hash_value.lower()

    # If not hex, check if base64
    if _is_likely_base64(hash_value):
        try:
            return convert_base64_to_hex(hash_value)
        except ValueError:
            # If base64 decode fails, return unchanged
            return hash_value

    # Unknown format - return unchanged
    return hash_value


def _extract_hash_from_dict(data: dict) -> tuple[str, HashType] | None:
    """Extract hash value and algorithm from a dictionary.

    Args:
        data: Dictionary containing hash information keyed by algorithm.

    Returns:
        A tuple of (normalized_hash_value, algorithm) or None if no hash found.
    """
    for algo in HASH_PREFERENCE_ORDER:
        if algo in data:
            return _normalize_hash_value(data[algo]), algo

    if data:
        first_key, first_value = next(iter(data.items()))
        return (
            _normalize_hash_value(first_value),
            first_key if isinstance(first_key, str) else DEFAULT_HASH_TYPE,
        )

    return None


def _is_yaml_content(content: str) -> bool:
    """Check if the content appears to be YAML format.

    Args:
        content: The content to check.

    Returns:
        True if the content is valid YAML and a dict, False otherwise.
    """
    if not _YAML_AVAILABLE:
        return False

    content_stripped = content.strip()
    if not content_stripped:
        return False

    try:
        data = yaml.safe_load(content_stripped)
        if isinstance(data, dict):
            logger.debug("   Detected YAML format checksum file")
            return True
    except yaml.YAMLError:
        pass

    return False


def _parse_yaml_root_level(
    data: dict, filename: str
) -> tuple[str, HashType] | None:
    """Parse YAML checksum file at root level.

    Args:
        data: The parsed YAML data.
        filename: The filename to find the hash for.

    Returns:
        A tuple of (hash_value, algorithm) or None if not found.
    """
    if "path" in data and data["path"] == filename:
        return _extract_hash_from_dict(data)

    return None


def _parse_yaml_files_dict(
    files: dict, filename: str
) -> tuple[str, HashType] | None:
    """Parse YAML files section when it's a dictionary.

    Args:
        files: The files dictionary from YAML.
        filename: The filename to find.

    Returns:
        A tuple of (hash_value, algorithm) or None.
    """
    hash_value = files.get(filename)
    if not hash_value:
        return None

    if isinstance(hash_value, str):
        return _normalize_hash_value(hash_value), YAML_DEFAULT_HASH
    if isinstance(hash_value, dict):
        return _extract_hash_from_dict(hash_value)

    return None


def _parse_yaml_files_list(
    files: list, filename: str
) -> tuple[str, HashType] | None:
    """Parse YAML files section when it's a list.

    Args:
        files: The files list from YAML.
        filename: The filename to find.

    Returns:
        A tuple of (hash_value, algorithm) or None.
    """
    for file_entry in files:
        if not isinstance(file_entry, dict):
            continue

        file_name = file_entry.get("name") or file_entry.get("url")
        if file_name != filename:
            continue

        preferred = _extract_hash_from_dict(file_entry)
        if preferred:
            return preferred

    return None


def _parse_yaml_checksum_file(
    content: str, filename: str
) -> tuple[str, HashType] | None:
    """Parse a YAML checksum file.

    Args:
        content: The YAML content as string.
        filename: The filename to find the hash for.

    Returns:
        Tuple of (hash_value, algorithm) or None.
    """
    if not _YAML_AVAILABLE:
        logger.warning("⚠️  YAML parsing not available")
        return None

    try:
        data = yaml.safe_load(content)
        logger.debug("   Parsed YAML checksum file")
        logger.debug("   Structure keys: %s", list(data.keys()))

        if "files" not in data:
            return _parse_yaml_root_level(data, filename)

        files = data["files"]
        logger.debug("   Files section type: %s", type(files))
        logger.debug("   Looking for: %s", filename)

        if isinstance(files, dict):
            return _parse_yaml_files_dict(files, filename)
        if isinstance(files, list):
            return _parse_yaml_files_list(files, filename)
        return None  # noqa: TRY300 - multiple early returns in try block
    except yaml.YAMLError:
        logger.exception("❌ Failed to parse YAML checksum file")
        return None


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


class YAMLChecksumParser(ChecksumParser):
    """Parser for electron-builder style YAML checksum files."""

    def parse(
        self, content: str, filename: str, _hash_type: HashType | None = None
    ) -> ChecksumEntry | None:
        """Parse YAML checksum content.

        Args:
            content: The YAML content.
            filename: The filename to find.
            _hash_type: Unused for YAML parser (required by interface).

        Returns:
            A ChecksumEntry or None.
        """
        parsed = _parse_yaml_checksum_file(content, filename)
        if not parsed:
            return None

        hash_value, algorithm = parsed
        return ChecksumEntry(filename, hash_value, algorithm)


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
    if _is_yaml_content(content):
        parser: ChecksumParser = YAMLChecksumParser()
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


def detect_hash_type_from_checksum_filename(filename: str) -> HashType | None:
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


def _parse_all_yaml_checksums(content: str) -> dict[str, str]:
    """Parse all filename-to-hash mappings from YAML checksum format.

    Args:
        content: The YAML checksum file content.

    Returns:
        Dictionary mapping filenames to hash values.

    """
    if not _YAML_AVAILABLE or not yaml:
        return {}

    hashes: dict[str, str] = {}

    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return {}

        for filename, hash_data in data.items():
            if isinstance(hash_data, dict):
                result = _extract_hash_from_dict(hash_data)
                if result:
                    hash_value, _ = result
                    hashes[filename] = hash_value
            elif isinstance(hash_data, str):
                hashes[filename] = _normalize_hash_value(hash_data)

    except yaml.YAMLError:
        logger.debug("Failed to parse YAML for all checksums")
        return {}

    return hashes


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
