"""Tests for BackupService restore functionality.

Tests for restore operations, integrity verification, and edge case handling.
"""

from typing import Any

from my_unicorn.core.backup import BackupMetadata


class TestBackupServiceRestore:
    """Test BackupService restore functionality."""

    def test_restore_latest_backup(
        self,
        backup_service: Any,
        dummy_config: Any,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test restoring the latest backup."""
        config_manager, _, backup_dir, storage_dir = dummy_config
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
        self,
        backup_service: Any,
        dummy_config: Any,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test that current version is backed up before restore."""
        config_manager, _, backup_dir, storage_dir = dummy_config
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

    def test_restore_missing_app_config(
        self, backup_service: Any, dummy_config: Any
    ) -> None:
        """Test restore when app config is missing."""
        config_manager, _, _, storage_dir = dummy_config
        config_manager.load_app_config.return_value = None

        result = backup_service.restore_latest_backup(
            "nonexistent", storage_dir
        )
        assert result is None

    def test_restore_backup_integrity_failure(
        self,
        backup_service: Any,
        dummy_config: Any,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test restore when backup integrity check fails."""
        config_manager, _, backup_dir, storage_dir = dummy_config
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
        self,
        backup_service: Any,
        dummy_config: Any,
        sample_v1_app_config: dict[str, Any],
    ) -> None:
        """Test restore when app has v1 config format."""
        config_manager, _, backup_dir, storage_dir = dummy_config

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
        self,
        backup_service: Any,
        dummy_config: Any,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test that restore doesn't delete backup being restored on cleanup.

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
