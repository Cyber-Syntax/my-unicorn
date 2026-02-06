"""Helper functions for backup operations including validation and cleanup.

This module provides utilities for:
- Validating backup file existence and integrity
- Grouping backups by version
- Deleting old backup files
"""

from pathlib import Path
from typing import TYPE_CHECKING

from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from my_unicorn.core.backup.metadata import BackupMetadata

logger = get_logger(__name__)


def validate_backup_exists(backup_path: Path) -> None:
    """Validate that backup file exists.

    Args:
        backup_path: Path to backup file

    Raises:
        FileNotFoundError: If backup file doesn't exist
    """
    if not backup_path.exists():
        msg = f"Backup file not found: {backup_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)


def validate_backup_integrity(
    metadata: "BackupMetadata", version: str, backup_path: Path
) -> None:
    """Validate backup file integrity using checksum.

    Args:
        metadata: BackupMetadata instance
        version: Version string
        backup_path: Path to backup file

    Raises:
        ValueError: If integrity check fails
    """
    if not metadata.verify_backup_integrity(version, backup_path):
        msg = f"Backup integrity check failed for version {version}"
        logger.error(msg)
        raise ValueError(msg)


def group_backups_by_version(backups: list[Path]) -> dict[str, list[Path]]:
    """Group backup files by version number.

    Args:
        backups: List of backup file paths

    Returns:
        Dictionary mapping version strings to lists of backup paths
    """
    min_version_parts = 2
    version_groups: dict[str, list[Path]] = {}
    for backup in backups:
        # Extract version from backup filename (format: app-version.AppImage)
        parts = backup.stem.split("-")
        if len(parts) >= min_version_parts:
            version = parts[-1]
            version_groups.setdefault(version, []).append(backup)
    return version_groups


def delete_old_backups(
    versions_to_remove: list[str],
    metadata: "BackupMetadata",
    app_backup_dir: Path,
) -> None:
    """Delete old backup files and update metadata.

    Args:
        versions_to_remove: List of version strings to remove
        metadata: BackupMetadata instance
        app_backup_dir: Backup directory for the app
    """
    for version in versions_to_remove:
        version_info = metadata.get_version_info(version)
        if version_info:
            backup_path = app_backup_dir / version_info["filename"]
            if backup_path.exists():
                try:
                    backup_path.unlink()
                    metadata.remove_version(version)
                    logger.info(
                        "Removed old backup: %s (v%s)",
                        backup_path,
                        version,
                    )
                except OSError:
                    logger.exception("Failed to remove backup %s", backup_path)
