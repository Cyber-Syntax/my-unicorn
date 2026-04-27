"""Tests for backup helper functions."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.core.backup import (
    delete_old_backups,
    validate_backup_exists,
    validate_backup_integrity,
)


class TestValidateBackupExists:
    """Tests for validate_backup_exists function."""

    def test_exists(self, tmp_path: Path) -> None:
        """Test validation passes when backup file exists."""
        backup_path = tmp_path / "app-1.0.0.AppImage"
        backup_path.touch()
        validate_backup_exists(backup_path)

    def test_not_exists(self, tmp_path: Path) -> None:
        """Test validation fails when backup file doesn't exist."""
        backup_path = tmp_path / "nonexistent-1.0.0.AppImage"
        with pytest.raises(FileNotFoundError, match="Backup file not found"):
            validate_backup_exists(backup_path)


class TestValidateBackupIntegrity:
    """Tests for validate_backup_integrity function."""

    def test_valid_integrity(self, tmp_path: Path) -> None:
        """Test validation passes when integrity check succeeds."""
        backup_path = tmp_path / "app-1.0.0.AppImage"
        backup_path.touch()
        metadata_mock = MagicMock()
        metadata_mock.verify_backup_integrity.return_value = True
        validate_backup_integrity(metadata_mock, "1.0.0", backup_path)
        metadata_mock.verify_backup_integrity.assert_called_once_with(
            "1.0.0", backup_path
        )

    def test_invalid_integrity(self, tmp_path: Path) -> None:
        """Test validation fails when integrity check fails."""
        backup_path = tmp_path / "app-1.0.0.AppImage"
        backup_path.touch()
        metadata_mock = MagicMock()
        metadata_mock.verify_backup_integrity.return_value = False
        with pytest.raises(ValueError, match="Backup integrity check failed"):
            validate_backup_integrity(metadata_mock, "1.0.0", backup_path)


class TestDeleteOldBackups:
    """Tests for delete_old_backups function."""

    def test_successful_deletion(self, tmp_path: Path) -> None:
        """Test successful deletion of old backups."""
        backup_file = tmp_path / "app-1.0.0.AppImage"
        backup_file.touch()
        metadata_mock = MagicMock()
        metadata_mock.get_version_info.return_value = {
            "filename": "app-1.0.0.AppImage"
        }
        delete_old_backups(["1.0.0"], metadata_mock, tmp_path)
        assert not backup_file.exists()
        metadata_mock.remove_version.assert_called_once_with("1.0.0")

    def test_version_info_not_found(self, tmp_path: Path) -> None:
        """Test deletion when version info is not found."""
        metadata_mock = MagicMock()
        metadata_mock.get_version_info.return_value = None
        delete_old_backups(["1.0.0"], metadata_mock, tmp_path)
        metadata_mock.remove_version.assert_not_called()

    def test_file_not_exists(self, tmp_path: Path) -> None:
        """Test deletion prunes metadata when backup file doesn't exist."""
        metadata_mock = MagicMock()
        metadata_mock.get_version_info.return_value = {
            "filename": "nonexistent-1.0.0.AppImage"
        }
        delete_old_backups(["1.0.0"], metadata_mock, tmp_path)
        metadata_mock.remove_version.assert_called_once_with("1.0.0")

    def test_deletion_error_handling(self, tmp_path: Path) -> None:
        """Test handling when file deletion raises OSError."""
        backup_file = tmp_path / "app-1.0.0.AppImage"
        backup_file.touch()
        metadata_mock = MagicMock()
        metadata_mock.get_version_info.return_value = {
            "filename": "app-1.0.0.AppImage"
        }
        tmp_path.chmod(0o555)
        try:
            delete_old_backups(["1.0.0"], metadata_mock, tmp_path)
            assert backup_file.exists()
            metadata_mock.remove_version.assert_not_called()
        finally:
            tmp_path.chmod(0o755)
