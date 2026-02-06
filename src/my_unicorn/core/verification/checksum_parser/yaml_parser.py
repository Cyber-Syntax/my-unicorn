"""YAML checksum file parser implementation."""

from __future__ import annotations

from my_unicorn.constants import YAML_DEFAULT_HASH, HashType
from my_unicorn.core.verification.checksum_parser.base import (
    ChecksumEntry,
    ChecksumParser,
)
from my_unicorn.core.verification.checksum_parser.normalizer import (
    _extract_hash_from_dict,
    _normalize_hash_value,
)
from my_unicorn.logger import get_logger

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via patching in tests
    yaml = None
    _YAML_AVAILABLE = False


logger = get_logger(__name__)


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
