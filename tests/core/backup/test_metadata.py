"""Tests for BackupMetadata.

Tests for backup metadata creation, loading, version management,
and integrity verification.
"""

from pathlib import Path

from my_unicorn.core.backup import BackupMetadata


class TestBackupMetadata:
    """Test BackupMetadata functionality."""

    def test_metadata_creation_and_loading(self, tmp_path: Path) -> None:
        """Test creating and loading metadata."""
        metadata = BackupMetadata(tmp_path)

        # Test loading non-existent metadata
        data = metadata.load()
        assert data == {"versions": {}}

        # Add a version and save
        test_file = tmp_path / "test.AppImage"
        test_file.write_text("test content")
        metadata.add_version("1.0.0", "test-1.0.0.AppImage", test_file)

        # Load and verify
        data = metadata.load()
        assert "1.0.0" in data["versions"]
        assert data["versions"]["1.0.0"]["filename"] == "test-1.0.0.AppImage"
        assert "sha256" in data["versions"]["1.0.0"]
        assert "created" in data["versions"]["1.0.0"]
        assert "size" in data["versions"]["1.0.0"]

    def test_get_latest_version(self, tmp_path: Path) -> None:
        """Test getting latest version."""
        metadata = BackupMetadata(tmp_path)

        # No versions
        assert metadata.get_latest_version() is None

        # Add versions
        test_file = tmp_path / "test.AppImage"
        test_file.write_text("test")

        metadata.add_version("1.0.0", "test-1.0.0.AppImage", test_file)
        metadata.add_version("1.2.0", "test-1.2.0.AppImage", test_file)
        metadata.add_version("1.1.0", "test-1.1.0.AppImage", test_file)

        # Should return highest version
        assert metadata.get_latest_version() == "1.2.0"

    def test_list_versions_sorted(self, tmp_path: Path) -> None:
        """Test listing versions in sorted order."""
        metadata = BackupMetadata(tmp_path)

        test_file = tmp_path / "test.AppImage"
        test_file.write_text("test")

        versions = ["1.0.0", "2.1.0", "1.5.0"]
        for version in versions:
            metadata.add_version(
                version, f"test-{version}.AppImage", test_file
            )

        sorted_versions = metadata.list_versions()
        assert sorted_versions == ["2.1.0", "1.5.0", "1.0.0"]  # Newest first

    def test_corrupted_metadata_handling(self, tmp_path: Path) -> None:
        """Test handling of corrupted metadata files."""
        metadata = BackupMetadata(tmp_path)

        # Create corrupted metadata file
        metadata.metadata_file.write_text("invalid json {")

        # Should handle gracefully and return empty versions
        data = metadata.load()
        assert data == {"versions": {}}

        # Should create backup of corrupted file
        corrupted_backup = tmp_path / "metadata.json.corrupted"
        assert corrupted_backup.exists()

    def test_backup_integrity_verification(self, tmp_path: Path) -> None:
        """Test backup integrity verification using checksums."""
        # Create backup file
        backup_file = tmp_path / "app1-1.2.3.AppImage"
        backup_file.write_text("original content")

        metadata = BackupMetadata(tmp_path)
        metadata.add_version("1.2.3", "app1-1.2.3.AppImage", backup_file)

        # Verify integrity passes for unchanged file
        assert metadata.verify_backup_integrity("1.2.3", backup_file) is True

        # Modify file content
        backup_file.write_text("modified content")

        # Verify integrity fails for modified file
        assert metadata.verify_backup_integrity("1.2.3", backup_file) is False
