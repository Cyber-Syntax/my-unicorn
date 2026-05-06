"""Base classes and dataclasses for checksum parsing."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    HASH_PREFERENCE_ORDER,
    SUPPORTED_HASH_ALGORITHMS,
    YAML_CHECKSUM_EXTENSIONS,
    YAML_DEFAULT_HASH,
)
from my_unicorn.logger import get_logger

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via patching in tests
    yaml = None  # type: ignore[assignment]
    _YAML_AVAILABLE = False


if TYPE_CHECKING:
    from collections.abc import Iterable

    from my_unicorn.constants import HashType


logger = get_logger(__name__)


_HASH_LENGTH_MAP: dict[int, HashType] = {
    64: "sha256",
    128: "sha512",
}

_HASH_TYPE_LENGTH_MAP: dict[HashType, int] = {
    hash_type: length for length, hash_type in _HASH_LENGTH_MAP.items()
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
    }

    for hash_type, patterns in hash_patterns.items():
        if hash_type in SUPPORTED_HASH_ALGORITHMS and any(
            pattern in filename_lower for pattern in patterns
        ):
            return hash_type

    if filename_lower.endswith(YAML_CHECKSUM_EXTENSIONS):
        return YAML_DEFAULT_HASH

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
        normalized_hash = _normalize_hash_value(hash_value)
        return normalized_hash, YAML_DEFAULT_HASH
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


def _parse_all_yaml_checksums(content: str) -> dict[str, str]:
    """Parse all filename-to-hash mappings from YAML checksum format."""
    if not _YAML_AVAILABLE or not yaml:
        return {}

    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return {}
    except yaml.YAMLError:
        logger.debug("Failed to parse YAML for all checksums")
        return {}

    hashes: dict[str, str] = {}

    # electron-builder: files is a list of {url, sha512, size}
    files = data.get("files")
    if isinstance(files, list):
        for entry in files:
            if not isinstance(entry, dict):
                continue
            filename = entry.get("url") or entry.get("name")
            if not filename:
                continue
            result = _extract_hash_from_dict(entry)
            if result:
                hash_value, _ = result
                hashes[filename] = hash_value

    # Also capture root-level entry (primary file)
    root_path = data.get("path")
    if root_path:
        result = _extract_hash_from_dict(data)
        if result:
            hash_value, _ = result
            hashes[root_path] = hash_value

    # Fallback: generic {filename: hash_str} flat structure
    if not hashes:
        for key, value in data.items():
            if isinstance(value, str) and key not in (
                "version",
                "path",
                "releaseDate",
                "releaseNotes",
            ):
                hashes[key] = _normalize_hash_value(value)
            elif isinstance(value, dict):
                result = _extract_hash_from_dict(value)
                if result:
                    hash_value, _ = result
                    hashes[key] = hash_value

    return hashes


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

    Supported hexadecimal hash lengths:
    - SHA256: 64 characters
    - SHA512: 128 characters

    Unsupported but detected:
    - MD5: 32 characters
    - SHA1: 40 characters

    If MD5 or SHA1 is detected, a warning is logged and False is returned.

    Args:
        hash_value: The hash value to check.

    Returns:
        True if the hash appears to be a supported hexadecimal hash
        (SHA256 or SHA512), False otherwise.

    Examples:
        >>> _is_likely_hex("abc123def4567890abcdef1234567890")  # MD5
        False
        >>> _is_likely_hex("a" * 40)  # SHA1
        False
        >>> _is_likely_hex("deadbeef" * 8)  # SHA256
        True
        >>> _is_likely_hex("DEADBEEF" * 16)  # SHA512 uppercase
        True
    """
    hash_value = hash_value.strip()
    hash_length = len(hash_value)

    # First ensure all characters are valid hexadecimal
    if not all(c in "0123456789abcdefABCDEF" for c in hash_value):
        return False

    # Detect unsupported legacy hashes
    if hash_length == 32:
        logger.warning("MD5 hashes are no longer supported.")
        return False

    if hash_length == 40:
        logger.warning("SHA1 hashes are no longer supported.")
        return False

    # Supported hash algorithms
    if hash_length in (64, 128):
        return True

    return False


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
    # Type coercion: convert non-string input to string
    hash_value = str(hash_value)

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
        # Validate hash type
        validated_hash: HashType
        if isinstance(first_key, str) and first_key in (
            "sha256",
            "sha512",
        ):
            validated_hash = first_key  # type: ignore[assignment]
        else:
            validated_hash = DEFAULT_HASH_TYPE
        return (
            _normalize_hash_value(first_value),
            validated_hash,
        )

    return None
