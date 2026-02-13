"""Tests for BackupHandler backup list and info operations."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.cli.commands.backup import BackupHandler
from my_unicorn.core.backup import BackupMetadata


class TestBackupHandler:
    """Test BackupHandler backup list and info operations."""

    @pytest.mark.asyncio
    async def test_list_backups_for_app(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        temp_config: tuple,
    ) -> None:
        """Test listing backups for a specific app."""
        _, backup_dir, _ = temp_config

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backup versions using BackupMetadata for proper checksums
        versions = ["1.2.1", "1.2.2", "1.2.3"]
        metadata_manager = BackupMetadata(app_backup_dir)

        for version in versions:
            backup_file = app_backup_dir / f"{app_name}-{version}.AppImage"
            backup_file.write_text(f"content for {version}")
            metadata_manager.add_version(
                version, f"{app_name}-{version}.AppImage", backup_file
            )

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = True
        args.cleanup = False
        args.info = False

        # Execute and verify no exceptions
        await backup_handler.execute(args)

        # Verify the backups were properly listed by checking metadata
        metadata = metadata_manager.load()
        assert len(metadata["versions"]) == 3
        assert all(v in metadata["versions"] for v in versions)

    @pytest.mark.asyncio
    async def test_list_backups_for_nonexistent_app(
        self, backup_handler: BackupHandler, mock_config_manager: MagicMock
    ) -> None:
        """Test listing backups for a non-existent app."""
        args = MagicMock()
        args.app_name = "nonexistentapp"
        args.restore_last = False
        args.restore_version = None
        args.list_backups = True
        args.cleanup = False
        args.info = False

        # Should execute without error even if app has no backups
        await backup_handler.execute(args)

    def test_list_backups_requires_app_name(
        self, backup_handler: BackupHandler
    ) -> None:
        """Test that --list-backups requires app_name."""
        args = MagicMock()
        args.app_name = None
        args.restore_last = False
        args.restore_version = None
        args.list_backups = True
        args.cleanup = False
        args.info = False

        # Should fail validation
        result = backup_handler._validate_arguments(args)
        assert result is False

    @pytest.mark.asyncio
    async def test_info_command_with_backups(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        temp_config: tuple,
    ) -> None:
        """Test --info command shows detailed backup information."""
        _, backup_dir, _ = temp_config

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backups using BackupMetadata for proper structure
        versions = ["1.0.0", "1.1.0", "1.2.0"]
        metadata_manager = BackupMetadata(app_backup_dir)

        for version in versions:
            backup_file = app_backup_dir / f"{app_name}-{version}.AppImage"
            backup_file.write_text(f"content for version {version}")
            metadata_manager.add_version(
                version, f"{app_name}-{version}.AppImage", backup_file
            )

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True

        # Execute and verify no exceptions
        await backup_handler.execute(args)

        # Verify backup info is accessible
        backup_info = backup_handler.backup_service.get_backup_info(  # type: ignore[attr-defined]
            app_name
        )
        assert len(backup_info) == 3
        assert all(info["version"] in versions for info in backup_info)

    @pytest.mark.asyncio
    async def test_info_command_no_backups(
        self, backup_handler: BackupHandler, mock_config_manager: MagicMock
    ) -> None:
        """Test --info command when app has no backups."""
        args = MagicMock()
        args.app_name = "appwithnobackups"
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True

        # Should execute without error even if no backups exist
        await backup_handler.execute(args)

    def test_info_requires_app_name(
        self, backup_handler: BackupHandler
    ) -> None:
        """Test that --info requires app_name."""
        args = MagicMock()
        args.app_name = None
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True

        # Should fail validation
        result = backup_handler._validate_arguments(args)
        assert result is False
