"""Base migration utilities.

Common functionality shared across all migration modules:
- Version comparison
- Backup creation
- JSON file operations
"""

from pathlib import Path
from typing import Any

import orjson

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic version strings.

    Args:
        version1: First version string (e.g., "1.0.0")
        version2: Second version string (e.g., "1.0.1")

    Returns:
        -1 if version1 < version2, 0 if equal, 1 if version1 > version2

    """

    def parse_version(version: str) -> list[int]:
        """Parse version string into list of integers."""
        try:
            return [int(x) for x in version.split(".")]
        except ValueError:
            # Fallback for invalid versions
            return [0, 0, 0]

    v1_parts = parse_version(version1)
    v2_parts = parse_version(version2)

    # Pad shorter version with zeros
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))

    for v1, v2 in zip(v1_parts, v2_parts, strict=True):
        if v1 < v2:
            return -1
        if v1 > v2:
            return 1
    return 0


def needs_migration(current_version: str, target_version: str) -> bool:
    """Check if migration is needed.

    Args:
        current_version: Current config version
        target_version: Target version to migrate to

    Returns:
        True if migration needed

    """
    return compare_versions(current_version, target_version) < 0


def create_backup(file_path: Path, backup_dir: Path | None = None) -> Path:
    """Create backup of a config file.

    Args:
        file_path: Path to file to backup
        backup_dir: Optional backup directory
            (default: file_path.parent / 'backups')

    Returns:
        Path to backup file

    """
    if backup_dir is None:
        backup_dir = file_path.parent / "backups"

    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"{file_path.name}.backup"

    # Read and write to preserve exact format
    with file_path.open("rb") as f:
        content = f.read()

    with backup_file.open("wb") as f:
        f.write(content)

    logger.info("Created backup: %s", backup_file)
    return backup_file


def load_json_file(file_path: Path) -> dict[str, Any]:
    """Load JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is invalid

    """
    if not file_path.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)

    try:
        with file_path.open("rb") as f:
            return orjson.loads(f.read())  # type: ignore[no-any-return]
    except orjson.JSONDecodeError as e:
        msg = f"Invalid JSON in {file_path}: {e}"
        raise ValueError(msg) from e


def save_json_file(file_path: Path, data: dict[str, Any]) -> None:
    """Save data to JSON file with formatting.

    Args:
        file_path: Path to save JSON file
        data: Data to save

    """
    with file_path.open("wb") as f:
        f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    logger.debug("Saved JSON to %s", file_path)
