"""Tests for BackupHandler backup cleanup operations."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.cli.commands.backup import BackupHandler
from my_unicorn.core.backup import BackupMetadata


class TestBackupHandler:
    """Test BackupHandler backup cleanup operations."""

    @pytest.mark.asyncio
    async def test_cleanup_backups_specific_app(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        temp_config: tuple,
    ) -> None:
        """Test cleanup of old backups for a specific app."""
        global_config, backup_dir, _ = temp_config
        global_config["max_backup"] = 2

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create multiple backup versions using BackupMetadata
        versions = ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]
        metadata_manager = BackupMetadata(app_backup_dir)

        for version in versions:
            backup_file = app_backup_dir / f"{app_name}-{version}.AppImage"
            backup_file.write_text(f"content {version}")
            metadata_manager.add_version(
                version, f"{app_name}-{version}.AppImage", backup_file
            )

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = True
        args.info = False

        await backup_handler.execute(args)

        # Should keep only max_backup (2) files
        remaining_files = list(app_backup_dir.glob("*.AppImage"))
        assert len(remaining_files) <= 2

        # Verify metadata was updated
        updated_metadata = metadata_manager.load()
        assert len(updated_metadata["versions"]) <= 2

    @pytest.mark.asyncio
    async def test_cleanup_backups_global(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        temp_config: tuple,
    ) -> None:
        """Test cleanup of old backups for all apps."""
        global_config, backup_dir, _ = temp_config
        global_config["max_backup"] = 1

        # Create backup directories for multiple apps
        apps = ["appflowy", "obsidian"]

        for app_name in apps:
            app_backup_dir = backup_dir / app_name
            app_backup_dir.mkdir(parents=True)

            # Create multiple backups for each app
            versions = ["1.0.0", "1.1.0"]
            metadata_manager = BackupMetadata(app_backup_dir)

            for version in versions:
                backup_file = app_backup_dir / f"{app_name}-{version}.AppImage"
                backup_file.write_text(f"content {version}")
                metadata_manager.add_version(
                    version, f"{app_name}-{version}.AppImage", backup_file
                )

        args = MagicMock()
        args.app_name = None  # Global cleanup
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = True
        args.info = False

        await backup_handler.execute(args)

        # Each app should have only max_backup (1) files
        for app_name in apps:
            app_backup_dir = backup_dir / app_name
            remaining_files = list(app_backup_dir.glob("*.AppImage"))
            assert len(remaining_files) <= 1

    @pytest.mark.asyncio
    async def test_cleanup_zero_max_backup(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        temp_config: tuple,
    ) -> None:
        """Test cleanup when max_backup is set to 0 (remove all)."""
        global_config, backup_dir, _ = temp_config
        global_config["max_backup"] = 0

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backups using BackupMetadata
        versions = ["1.0.0", "1.1.0"]
        metadata_manager = BackupMetadata(app_backup_dir)

        for version in versions:
            backup_file = app_backup_dir / f"{app_name}-{version}.AppImage"
            backup_file.write_text(f"content {version}")
            metadata_manager.add_version(
                version, f"{app_name}-{version}.AppImage", backup_file
            )

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = True
        args.info = False

        await backup_handler.execute(args)

        # All backups should be removed
        remaining_files = list(app_backup_dir.glob("*.AppImage"))
        assert len(remaining_files) == 0

        # Metadata file should also be removed
        assert not (app_backup_dir / "metadata.json").exists()
