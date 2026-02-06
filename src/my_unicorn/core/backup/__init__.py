"""Backup module for managing AppImage backups and version recovery.

Provides services for creating, managing, and restoring AppImage backups
with version tracking, integrity verification, and metadata management.

Public API:
    - BackupService: Main service for backup operations
    - BackupMetadata: Metadata management for backups
    - restore_latest_backup: Function to restore latest backup version
    - restore_specific_version: Function to restore specific backup version
"""

from my_unicorn.core.backup.metadata import BackupMetadata
from my_unicorn.core.backup.restore import (
    restore_latest_backup,
    restore_specific_version,
)
from my_unicorn.core.backup.service import BackupService

__all__ = [
    "BackupMetadata",
    "BackupService",
    "restore_latest_backup",
    "restore_specific_version",
]
