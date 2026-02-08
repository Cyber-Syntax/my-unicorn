"""Tests for BackupService: enhanced backup creation, cleanup, restore, and migration."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import orjson
import pytest

from my_unicorn.core.backup import BackupMetadata, BackupService


@pytest.fixture
def dummy_config(tmp_path):
    """Provide dummy config_manager and global_config for BackupService."""
    backup_dir = tmp_path / "backups"
    storage_dir = tmp_path / "Applications"
    backup_dir.mkdir()
    storage_dir.mkdir()

    global_config = {
        "directory": {"backup": backup_dir, "storage": storage_dir},
        "max_backup": 2,
    }
    config_manager = MagicMock()
    config_manager.list_installed_apps.return_value = [
        "app1",
        "app2",
        "freetube",
    ]
    return config_manager, global_config, backup_dir, storage_dir


@pytest.fixture
def backup_service(dummy_config):
    config_manager, global_config, _, _ = dummy_config
    return BackupService(config_manager, global_config)


@pytest.fixture
def sample_app_config():
    """Sample app configuration for testing (v2 format)."""
    return {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "app1",
        "state": {
            "version": "1.2.3",
            "installed_date": "2024-08-19T12:50:44.179839",
            "installed_path": "/path/to/storage/app1.AppImage",
            "verification": {
                "passed": True,
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "abc123def456",
                        "computed": "abc123def456",
                        "source": "github_api",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/path/to/icon.png",
            },
        },
        "overrides": {
            "metadata": {
                "name": "app1",
                "display_name": "App1",
            },
            "source": {
                "type": "github",
                "owner": "owner",
                "repo": "repo",
                "prerelease": False,
            },
            "appimage": {
                "rename": "app1",
            },
            "verification": {
                "methods": ["digest"],
            },
            "icon": {
                "method": "extraction",
            },
        },
    }


@pytest.fixture
def sample_v1_app_config():
    """Sample app configuration for testing (v1 format - legacy)."""
    return {
        "config_version": "1.0.0",
        "appimage": {
            "version": "1.2.3",
            "name": "app1.AppImage",
            "rename": "app1",
            "installed_date": "2024-08-19T12:50:44.179839",
            "digest": "sha256:abc123def456",
        },
    }


class TestBackupMetadata:
    """Test BackupMetadata functionality."""

    def test_metadata_creation_and_loading(self, tmp_path):
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

    def test_get_latest_version(self, tmp_path):
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

    def test_list_versions_sorted(self, tmp_path):
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

    def test_corrupted_metadata_handling(self, tmp_path):
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


class TestBackupService:
    """Test enhanced BackupService functionality."""

    def test_create_backup_with_folder_structure(
        self, backup_service, dummy_config, sample_app_config
    ):
        """Test backup creation with new folder structure."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config
        config_manager.load_app_config.return_value = sample_app_config

        # Create source file
        file_path = storage_dir / "app1.AppImage"
        file_path.write_text("app content")

        # Create backup
        backup_path = backup_service.create_backup(file_path, "app1", "1.2.3")

        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.parent.name == "app1"  # App-specific folder
        assert backup_path.name == "app1-1.2.3.AppImage"
        assert backup_path.read_text() == "app content"

        # Verify metadata was created
        metadata_file = backup_path.parent / "metadata.json"
        assert metadata_file.exists()

        metadata = orjson.loads(metadata_file.read_bytes())
        assert "1.2.3" in metadata["versions"]

    def test_create_backup_missing_file(self, backup_service):
        """Test backup creation with missing source file."""
        file_path = Path("nonexistent.AppImage")
        backup = backup_service.create_backup(file_path, "app1")
        assert backup is None

    def test_restore_latest_backup(
        self, backup_service, dummy_config, sample_app_config
    ):
        """Test restoring the latest backup."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config
        config_manager.load_app_config.return_value = sample_app_config

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create backup file and metadata
        backup_file = app_backup_dir / "app1-1.2.2.AppImage"
        backup_file.write_text("backup content")

        metadata = BackupMetadata(app_backup_dir)
        metadata.add_version("1.2.2", "app1-1.2.2.AppImage", backup_file)

        # Restore
        restored_path = backup_service.restore_latest_backup(
            app_name, storage_dir
        )

        assert restored_path is not None
        assert restored_path.name == "app1.AppImage"
        assert restored_path.read_text() == "backup content"

        # Verify config was updated
        config_manager.save_app_config.assert_called()

    def test_restore_with_current_version_backup(
        self, backup_service, dummy_config, sample_app_config
    ):
        """Test that current version is backed up before restore."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config
        config_manager.load_app_config.return_value = sample_app_config

        app_name = "app1"

        # Create current file
        current_file = storage_dir / "app1.AppImage"
        current_file.write_text("current content")

        # Create backup to restore from
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        backup_file = app_backup_dir / "app1-1.2.1.AppImage"
        backup_file.write_text("old content")

        metadata = BackupMetadata(app_backup_dir)
        metadata.add_version("1.2.1", "app1-1.2.1.AppImage", backup_file)

        # Restore (should backup current version first)
        restored_path = backup_service.restore_specific_version(
            app_name, "1.2.1", storage_dir
        )

        assert restored_path is not None
        assert restored_path.read_text() == "old content"

        # Check that current version was backed up
        metadata_data = metadata.load()
        assert (
            "1.2.3" in metadata_data["versions"]
        )  # Current version from config

    def test_cleanup_old_backups_folder_structure(
        self, backup_service, dummy_config, sample_app_config
    ):
        """Test cleanup with new folder structure."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config
        global_config["max_backup"] = 2

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create multiple backups
        versions = ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]
        metadata = BackupMetadata(app_backup_dir)

        for i, version in enumerate(versions):
            backup_file = app_backup_dir / f"app1-{version}.AppImage"
            backup_file.write_text(f"content {version}")

            # Add to metadata with different timestamps for sorting
            metadata.add_version(
                version, f"app1-{version}.AppImage", backup_file
            )

            # Modify created timestamp for proper sorting
            metadata_data = metadata.load()
            timestamp = datetime.now() - timedelta(days=len(versions) - i - 1)
            metadata_data["versions"][version]["created"] = (
                timestamp.isoformat()
            )
            metadata.save(metadata_data)

        # Cleanup
        backup_service._cleanup_old_backups_for_app(app_backup_dir)

        # Should keep only 2 most recent
        remaining_files = list(app_backup_dir.glob("*.AppImage"))
        assert len(remaining_files) <= 2

        # Check metadata was updated
        metadata_data = metadata.load()
        assert len(metadata_data["versions"]) <= 2

    def test_cleanup_max_zero_removes_all(self, backup_service, dummy_config):
        """Test that max_backup=0 removes all backups."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config
        global_config["max_backup"] = 0

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create backups
        for version in ["1.0.0", "1.1.0", "1.2.0"]:
            backup_file = app_backup_dir / f"app1-{version}.AppImage"
            backup_file.write_text(f"content {version}")

            metadata = BackupMetadata(app_backup_dir)
            metadata.add_version(
                version, f"app1-{version}.AppImage", backup_file
            )

        backup_service._cleanup_old_backups_for_app(app_backup_dir)

        # All should be removed
        assert not list(app_backup_dir.glob("*.AppImage"))
        assert not (app_backup_dir / "metadata.json").exists()

    def test_get_backup_info_with_metadata(self, backup_service, dummy_config):
        """Test getting backup info from metadata."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create backup with metadata
        backup_file = app_backup_dir / "app1-1.2.3.AppImage"
        backup_file.write_text("content")

        metadata = BackupMetadata(app_backup_dir)
        metadata.add_version("1.2.3", "app1-1.2.3.AppImage", backup_file)

        result = backup_service.get_backup_info(app_name)

        assert len(result) == 1
        info = result[0]
        assert info["version"] == "1.2.3"
        assert info["filename"] == "app1-1.2.3.AppImage"
        assert info["exists"] is True
        assert "sha256" in info
        assert "size" in info
        assert "created" in info

    def test_list_apps_with_backups(self, backup_service, dummy_config):
        """Test listing apps that have backups."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config

        # Create backup directories for different apps
        apps_with_backups = ["app1", "app2"]

        for app_name in apps_with_backups:
            app_backup_dir = backup_dir / app_name
            app_backup_dir.mkdir()

            backup_file = app_backup_dir / f"{app_name}-1.0.0.AppImage"
            backup_file.write_text("content")

            metadata = BackupMetadata(app_backup_dir)
            metadata.add_version(
                "1.0.0", f"{app_name}-1.0.0.AppImage", backup_file
            )

        # Create empty directory (should be ignored)
        empty_dir = backup_dir / "empty_app"
        empty_dir.mkdir()

        result = backup_service.list_apps_with_backups()

        assert sorted(result) == sorted(apps_with_backups)
        assert "empty_app" not in result

    def test_backup_integrity_verification(self, backup_service, dummy_config):
        """Test backup integrity verification using checksums."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create backup file
        backup_file = app_backup_dir / "app1-1.2.3.AppImage"
        backup_file.write_text("original content")

        metadata = BackupMetadata(app_backup_dir)
        metadata.add_version("1.2.3", "app1-1.2.3.AppImage", backup_file)

        # Verify integrity passes for unchanged file
        assert metadata.verify_backup_integrity("1.2.3", backup_file) is True

        # Modify file content
        backup_file.write_text("modified content")

        # Verify integrity fails for modified file
        assert metadata.verify_backup_integrity("1.2.3", backup_file) is False

    def test_restore_missing_app_config(self, backup_service, dummy_config):
        """Test restore when app config is missing."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config
        config_manager.load_app_config.return_value = None

        result = backup_service.restore_latest_backup(
            "nonexistent", storage_dir
        )
        assert result is None

    def test_restore_backup_integrity_failure(
        self, backup_service, dummy_config, sample_app_config
    ):
        """Test restore when backup integrity check fails."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config
        config_manager.load_app_config.return_value = sample_app_config

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create backup file
        backup_file = app_backup_dir / "app1-1.2.1.AppImage"
        backup_file.write_text("original content")

        # Create metadata
        metadata = BackupMetadata(app_backup_dir)
        metadata.add_version("1.2.1", "app1-1.2.1.AppImage", backup_file)

        # Corrupt the backup file
        backup_file.write_text("corrupted content")

        # Restore should fail due to integrity check
        result = backup_service.restore_specific_version(
            app_name, "1.2.1", storage_dir
        )
        assert result is None

    def test_restore_v1_config_detected(
        self, backup_service, dummy_config, sample_v1_app_config
    ):
        """Test restore when app has v1 config format."""
        config_manager, global_config, backup_dir, storage_dir = dummy_config

        # Use v1 config fixture
        config_manager.load_app_config.return_value = sample_v1_app_config

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create backup file
        backup_file = app_backup_dir / "app1-1.2.1.AppImage"
        backup_file.write_text("backup content")

        # Create metadata
        metadata = BackupMetadata(app_backup_dir)
        metadata.add_version("1.2.1", "app1-1.2.1.AppImage", backup_file)

        # Restore should fail with v1 config message
        result = backup_service.restore_specific_version(
            app_name, "1.2.1", storage_dir
        )
        assert result is None

    def test_restore_doesnt_delete_restore_target(
        self, backup_service, dummy_config, sample_app_config
    ):
        """Test that restore doesn't delete the backup being restored during cleanup.

        Regression test for bug where cleanup ran during pre-restore backup
        creation, deleting the restore target before it could be restored.
        """
        config_manager, global_config, backup_dir, storage_dir = dummy_config

        # Configure max_backup=2 to trigger cleanup
        global_config["max_backup"] = 2
        config_manager.load_app_config.return_value = sample_app_config

        app_name = "app1"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir()

        # Create current AppImage
        current_appimage = storage_dir / "app1.AppImage"
        current_appimage.write_text("current version 1.2.3")

        # Create 3 backup files (older versions)
        backup_v120 = app_backup_dir / "app1-1.2.0.AppImage"
        backup_v121 = app_backup_dir / "app1-1.2.1.AppImage"
        backup_v122 = app_backup_dir / "app1-1.2.2.AppImage"

        backup_v120.write_text("backup content v1.2.0")
        backup_v121.write_text("backup content v1.2.1")
        backup_v122.write_text("backup content v1.2.2")

        # Create metadata with 3 versions
        metadata = BackupMetadata(app_backup_dir)
        metadata.add_version("1.2.2", "app1-1.2.2.AppImage", backup_v122)
        metadata.add_version("1.2.1", "app1-1.2.1.AppImage", backup_v121)
        metadata.add_version("1.2.0", "app1-1.2.0.AppImage", backup_v120)

        # Try to restore v1.2.0 (the oldest backup)
        # Before fix: cleanup during pre-restore backup would delete v1.2.0
        # causing FileNotFoundError
        # After fix: cleanup runs AFTER restore, so restore succeeds
        result = backup_service.restore_specific_version(
            app_name, "1.2.0", storage_dir
        )

        # Restore should succeed (the key fix!)
        assert result == current_appimage

        # Current version should be restored to v1.2.0
        assert current_appimage.read_text() == "backup content v1.2.0"

        # Check final backup state after cleanup
        # Should have: 1.2.3 (pre-restore backup) and 1.2.2
        # The oldest backups (1.2.0, 1.2.1) are removed AFTER restore
        final_metadata = BackupMetadata(app_backup_dir)
        final_versions = final_metadata.list_versions()

        # With max_backup=2, we should have only 2 backups after cleanup
        assert len(final_versions) == 2
        assert "1.2.3" in final_versions  # Pre-restore backup
        assert "1.2.2" in final_versions  # Second newest

        # v1.2.0 and v1.2.1 cleaned up AFTER successful restore
        assert "1.2.0" not in final_versions
        assert "1.2.1" not in final_versions
