"""Tests for BackupHandler backup restore operations."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.cli.commands.backup import BackupHandler
from my_unicorn.core.backup import BackupMetadata


class TestBackupHandler:
    """Test BackupHandler backup restore operations."""

    @pytest.mark.asyncio
    async def test_restore_last_success(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        sample_app_config: dict,
        temp_config: tuple,
    ) -> None:
        """Test successful restore of latest backup."""
        _, backup_dir, storage_dir = temp_config

        # Setup - create a backup first
        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backup file and metadata
        backup_file = app_backup_dir / f"{app_name}-1.2.2.AppImage"
        backup_file.write_text("backup content")

        # Use BackupMetadata to create proper checksums
        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version(
            "1.2.2", f"{app_name}-1.2.2.AppImage", backup_file
        )

        # Mock config manager
        mock_config_manager.load_app_config.return_value = sample_app_config

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = True
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = False

        # Execute
        await backup_handler.execute(args)

        # Verify file was restored
        restored_file = storage_dir / "appflowy.AppImage"
        assert restored_file.exists()
        assert restored_file.read_text() == "backup content"

        # Verify config was updated
        mock_config_manager.save_app_config.assert_called()

    @pytest.mark.asyncio
    async def test_restore_specific_version(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        sample_app_config: dict,
        temp_config: tuple,
    ) -> None:
        """Test restoring a specific version."""
        _, backup_dir, storage_dir = temp_config

        app_name = "appflowy"
        version = "1.2.1"

        # Setup backup
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        backup_file = app_backup_dir / f"{app_name}-{version}.AppImage"
        backup_file.write_text("specific version content")

        # Use BackupMetadata to create proper checksums
        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version(
            version, f"{app_name}-{version}.AppImage", backup_file
        )

        mock_config_manager.load_app_config.return_value = sample_app_config

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = version
        args.list_backups = False
        args.cleanup = False
        args.info = False

        await backup_handler.execute(args)

        # Verify specific version was restored
        restored_file = storage_dir / "appflowy.AppImage"
        assert restored_file.exists()
        assert restored_file.read_text() == "specific version content"

    @pytest.mark.asyncio
    async def test_backup_current_version_before_restore(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        sample_app_config: dict,
        temp_config: tuple,
    ) -> None:
        """Test that current version is backed up before restore."""
        _, backup_dir, storage_dir = temp_config

        app_name = "appflowy"

        # Create current AppImage
        current_appimage = storage_dir / "appflowy.AppImage"
        current_appimage.write_text("current version content")

        # Create backup to restore from
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        restore_version = "1.2.1"
        backup_file = app_backup_dir / f"{app_name}-{restore_version}.AppImage"
        backup_file.write_text("old version content")

        # Use BackupMetadata to create proper checksums
        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version(
            restore_version,
            f"{app_name}-{restore_version}.AppImage",
            backup_file,
        )

        # Mock config with different current version (v2 structure)
        current_config = sample_app_config.copy()
        current_config["state"] = current_config["state"].copy()
        current_config["state"]["version"] = (
            "1.2.3"  # Different from restore version
        )

        mock_config_manager.load_app_config.return_value = current_config

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = restore_version
        args.list_backups = False
        args.cleanup = False
        args.info = False

        await backup_handler.execute(args)

        # Verify current version was backed up
        metadata_manager = BackupMetadata(app_backup_dir)
        updated_metadata = metadata_manager.load()
        assert (
            "1.2.3" in updated_metadata["versions"]
        )  # Current version should now be in backups

        # Verify old version was restored
        assert current_appimage.read_text() == "old version content"
