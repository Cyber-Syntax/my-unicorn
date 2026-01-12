"""Base migration utilities.

Common functionality shared across all migration modules:
- Version comparison
- Backup creation
- JSON file operations
"""

from pathlib import Path
from typing import Any

import orjson

from my_unicorn.domain.version import compare_versions
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


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
