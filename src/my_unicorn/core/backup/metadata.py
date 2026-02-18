"""Backup metadata management for versioning and integrity verification.

This module handles:
- Loading and saving backup metadata JSON files
- Tracking backup versions and checksums
- SHA256 calculation for integrity verification
- Version sorting with semantic versioning fallback
"""

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

import orjson
from packaging.version import InvalidVersion, Version

from my_unicorn.constants import (
    BACKUP_METADATA_CORRUPTED_SUFFIX,
    BACKUP_METADATA_FILENAME,
    BACKUP_METADATA_TMP_PREFIX,
    BACKUP_METADATA_TMP_SUFFIX,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils.datetime_utils import get_current_datetime_local_iso

logger = get_logger(__name__)


class BackupMetadata:
    """Manages backup metadata for version tracking and integrity."""

    def __init__(self, backup_dir: Path) -> None:
        """Initialize metadata manager.

        Args:
            backup_dir: Directory containing app backups

        """
        self.backup_dir = backup_dir
        self.metadata_file = backup_dir / BACKUP_METADATA_FILENAME

    def load(self) -> dict[str, Any]:
        """Load metadata from file.

        Returns:
            Metadata dictionary with versions and file info

        """
        if not self.metadata_file.exists():
            return {"versions": {}}

        try:
            with self.metadata_file.open("rb") as f:
                data: dict[str, Any] = orjson.loads(f.read())
                return data
        except (orjson.JSONDecodeError, OSError) as e:
            logger.warning(
                "Corrupted metadata file %s: %s", self.metadata_file, e
            )
            # Create backup of corrupted file
            corrupted_backup = self.metadata_file.with_suffix(
                BACKUP_METADATA_CORRUPTED_SUFFIX
            )
            if self.metadata_file.exists():
                shutil.copy2(self.metadata_file, corrupted_backup)
                logger.info(
                    "Backed up corrupted metadata to %s", corrupted_backup
                )
            return {"versions": {}}

    def save(self, metadata: dict[str, Any]) -> None:
        """Save metadata to file atomically.

        Args:
            metadata: Metadata dictionary to save

        """
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first for atomic operation
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=self.backup_dir,
            prefix=BACKUP_METADATA_TMP_PREFIX,
            suffix=BACKUP_METADATA_TMP_SUFFIX,
            delete=False,
        ) as tmp_file:
            tmp_file.write(
                orjson.dumps(
                    metadata,
                    option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
                )
            )
            tmp_file.flush()
            temp_path = Path(tmp_file.name)

        # Atomic move
        temp_path.replace(self.metadata_file)
        logger.debug("Saved metadata to %s", self.metadata_file)

    def add_version(
        self, version: str, filename: str, file_path: Path
    ) -> None:
        """Add a version entry to metadata with checksum.

        Args:
            version: Version string
            filename: Name of the backup file
            file_path: Path to the backup file for checksum calculation

        """
        metadata = self.load()

        # Calculate checksum
        sha256_hash = self._calculate_sha256(file_path)

        # Add version entry
        metadata["versions"][version] = {
            "filename": filename,
            "sha256": sha256_hash,
            # Use local timezone for created timestamp
            "created": get_current_datetime_local_iso(),
            "size": file_path.stat().st_size,
        }

        self.save(metadata)
        logger.debug("Added version %s to metadata", version)

    def _sort_versions(
        self, versions: list[str], *, reverse: bool = True
    ) -> list[str]:
        """Sort versions using semantic versioning with fallback.

        Args:
            versions: List of version strings to sort
            reverse: Sort in descending order (newest first) if True

        Returns:
            Sorted list of version strings

        """
        if not versions:
            return []

        try:
            return sorted(versions, key=Version, reverse=reverse)
        except InvalidVersion:
            logger.warning(
                "Invalid version format detected, using lexicographic sorting"
            )
            return sorted(versions, reverse=reverse)

    def get_latest_version(self) -> str | None:
        """Get the latest version from metadata.

        Returns:
            Latest version string or None if no versions exist

        """
        metadata = self.load()
        versions = list(metadata["versions"].keys())

        if not versions:
            return None

        sorted_versions = self._sort_versions(versions, reverse=True)
        return sorted_versions[0]

    def get_version_info(self, version: str) -> dict[str, Any] | None:
        """Get information for a specific version.

        Args:
            version: Version string to look up

        Returns:
            Version information dictionary or None if not found

        """
        metadata = self.load()
        version_info: dict[str, Any] | None = metadata["versions"].get(version)
        return version_info

    def list_versions(self) -> list[str]:
        """List all available versions sorted by version number.

        Returns:
            List of version strings sorted newest to oldest

        """
        metadata = self.load()
        versions = list(metadata["versions"].keys())
        return self._sort_versions(versions, reverse=True)

    def remove_version(self, version: str) -> bool:
        """Remove a version from metadata.

        Args:
            version: Version to remove

        Returns:
            True if version was removed, False if not found

        """
        metadata = self.load()
        if version in metadata["versions"]:
            del metadata["versions"][version]
            self.save(metadata)
            logger.debug("Removed version %s from metadata", version)
            return True
        return False

    def verify_backup_integrity(self, version: str, file_path: Path) -> bool:
        """Verify backup file integrity using stored checksum.

        Args:
            version: Version to verify
            file_path: Path to backup file

        Returns:
            True if integrity check passes, False otherwise

        """
        version_info = self.get_version_info(version)
        if not version_info or not file_path.exists():
            return False

        stored_hash = version_info.get("sha256")
        if not stored_hash:
            logger.warning("No checksum stored for version %s", version)
            return False

        actual_hash = self._calculate_sha256(file_path)
        is_valid: bool = actual_hash == stored_hash

        if not is_valid:
            logger.error(
                "Integrity check failed for %s: expected %s, got %s",
                file_path,
                stored_hash,
                actual_hash,
            )

        return is_valid

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            SHA256 checksum as hex string

        """
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
