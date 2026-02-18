"""Tests for BackupHandler validation and integration operations."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.cli.commands.backup import BackupHandler
from my_unicorn.core.backup import BackupMetadata


class TestBackupHandler:
    """Test BackupHandler validation and integration operations."""

    def test_validate_arguments_missing_app_name(
        self, backup_handler: BackupHandler
    ) -> None:
        """Test argument validation when app_name is missing."""
        args = MagicMock()
        args.app_name = None
        args.restore_last = True
        args.list_backups = False
        args.cleanup = False

        # Should fail validation
        result = backup_handler._validate_arguments(args)
        assert result is False

    def test_validate_arguments_global_operations_no_app_name(
        self, backup_handler: BackupHandler
    ) -> None:
        """Test validation for global operations without needing app_name."""
        # Test global cleanup
        args = MagicMock()
        args.app_name = None
        args.list_backups = False
        args.cleanup = True

        result = backup_handler._validate_arguments(args)
        assert result is True

    def test_validate_arguments_invalid_app_name(
        self, backup_handler: BackupHandler
    ) -> None:
        """Test argument validation with invalid app name."""
        args = MagicMock()
        args.app_name = "app/with/slashes"
        args.restore_last = True
        args.list_backups = False
        args.cleanup = False

        result = backup_handler._validate_arguments(args)
        assert result is False

    def test_all_commands_require_app_name_except_global_operations(
        self, backup_handler: BackupHandler
    ) -> None:
        """Test that all commands except global operations require app_name."""
        # Commands that should require app_name
        required_app_name_commands: list[dict[str, bool | str]] = [
            {"restore_last": True},
            {"restore_version": "1.0.0"},
            {"list_backups": True},
            {"info": True},
            {"cleanup": True, "app_name": "test"},  # Specific app cleanup
        ]

        for command_args in required_app_name_commands:
            args = MagicMock()
            args.app_name = None
            args.restore_last = False
            args.restore_version = None
            args.list_backups = False
            args.cleanup = False
            args.info = False
            args.migrate = False

            # Set the specific command
            for key, value in command_args.items():
                if key != "app_name":
                    setattr(args, key, value)

            # Should fail validation for commands requiring app_name
            if "app_name" not in command_args:
                result = backup_handler._validate_arguments(args)
                assert result is False, (
                    f"Command {command_args} should require app_name"
                )

        # Commands that don't require app_name (global operations)
        global_operations: list[dict[str, bool | str]] = [
            {"cleanup": True},  # Global cleanup
        ]

        for command_args in global_operations:
            args = MagicMock()
            args.app_name = None
            args.restore_last = False
            args.restore_version = None
            args.list_backups = False
            args.cleanup = False
            args.info = False

            # Set the specific command
            for key, value in command_args.items():
                setattr(args, key, value)

            result = backup_handler._validate_arguments(args)
            assert result is True, (
                f"Global operation {command_args} should not require app_name"
            )

    @pytest.mark.asyncio
    async def test_commands_produce_visible_output(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        temp_config: tuple,
        mocker: MagicMock,
    ) -> None:
        """Test that commands produce visible output."""
        _, backup_dir, _ = temp_config

        # Create test backup data
        app_name = "testapp"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        backup_file = app_backup_dir / f"{app_name}-1.2.3.AppImage"
        backup_file.write_text("test content")

        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version(
            "1.2.3", f"{app_name}-1.2.3.AppImage", backup_file
        )

        mock_logger = mocker.patch("my_unicorn.cli.commands.backup.logger")

        # Test --info command output
        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True

        await backup_handler.execute(args)

        mock_logger.info.assert_any_call(
            "\n📊 Backup Statistics for %s:", "testapp"
        )
        mock_logger.info.assert_any_call("  📦 Total backups: %s", 1)
        mock_logger.info.assert_any_call("\n⚙️  Configuration:")

        # Test --list-backups command output
        mock_logger.reset_mock()
        args.info = False
        args.list_backups = True

        await backup_handler.execute(args)

        mock_logger.info.assert_any_call(
            "\nAvailable backups for %s:", "testapp"
        )
        mock_logger.info.assert_any_call("  %s v%s", mocker.ANY, "1.2.3")
        mock_logger.info.assert_any_call("     SHA256: %s...", mocker.ANY)

        # Test --cleanup command output
        mock_logger.reset_mock()
        args.list_backups = False
        args.cleanup = True

        await backup_handler.execute(args)

        mock_logger.info.assert_any_call(
            "🔄 Cleaning up old backups%s...", " for testapp"
        )
        mock_logger.info.assert_any_call(
            "✅ Cleanup completed (keeping %s most recent backups)", 3
        )
