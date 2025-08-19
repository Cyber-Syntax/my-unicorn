"""Tests for BackupHandler command: comprehensive testing of backup operations."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from my_unicorn.backup import BackupService
from my_unicorn.commands.backup import BackupHandler


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    config_manager = MagicMock()
    config_manager.list_installed_apps.return_value = ["appflowy", "freetube", "obsidian"]
    return config_manager


@pytest.fixture
def mock_auth_manager():
    """Mock authentication manager."""
    return MagicMock()


@pytest.fixture
def mock_update_manager():
    """Mock update manager."""
    return MagicMock()


@pytest.fixture
def temp_config(tmp_path):
    """Create temporary configuration with backup directory."""
    backup_dir = tmp_path / "backups"
    storage_dir = tmp_path / "Applications"

    backup_dir.mkdir(parents=True)
    storage_dir.mkdir(parents=True)

    global_config = {
        "directory": {
            "backup": backup_dir,
            "storage": storage_dir,
        },
        "max_backup": 3,
    }
    return global_config, backup_dir, storage_dir


@pytest.fixture
def backup_handler(mock_config_manager, mock_auth_manager, mock_update_manager, temp_config):
    """Create BackupHandler instance with mocked dependencies."""
    global_config, _, _ = temp_config
    handler = BackupHandler(mock_config_manager, mock_auth_manager, mock_update_manager)
    handler.global_config = global_config
    handler.backup_service = BackupService(mock_config_manager, global_config)
    return handler


@pytest.fixture
def sample_app_config():
    """Sample app configuration."""
    return {
        "config_version": "1.0.0",
        "source": "catalog",
        "appimage": {
            "version": "1.2.3",
            "name": "appflowy.AppImage",
            "rename": "appflowy",
            "name_template": "",
            "characteristic_suffix": [],
            "installed_date": "2024-08-19T12:50:44.179839",
            "digest": "sha256:abc123def456",
        },
        "owner": "AppFlowy-IO",
        "repo": "AppFlowy",
        "github": {"repo": True, "prerelease": False},
        "verification": {"digest": True, "skip": False},
        "icon": {"name": "appflowy.png", "url": "", "path": "/path/to/icon.png"},
    }


class TestBackupHandler:
    """Test BackupHandler command functionality."""

    @pytest.mark.asyncio
    async def test_create_backup_success(
        self, backup_handler, mock_config_manager, sample_app_config, temp_config
    ):
        """Test successful backup creation."""
        global_config, backup_dir, storage_dir = temp_config

        # Setup
        app_name = "appflowy"
        appimage_path = storage_dir / "appflowy.AppImage"
        appimage_path.write_text("fake appimage content")

        mock_config_manager.load_app_config.return_value = sample_app_config

        # Create args namespace
        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = False
        args.migrate = False

        # Execute
        await backup_handler.execute(args)

        # Verify backup was created
        app_backup_dir = backup_dir / app_name
        assert app_backup_dir.exists()

        backup_files = list(app_backup_dir.glob("*.AppImage"))
        assert len(backup_files) == 1
        assert backup_files[0].name == f"{app_name}-1.2.3.AppImage"

        # Verify metadata was created
        metadata_file = app_backup_dir / "metadata.json"
        assert metadata_file.exists()

        metadata = json.loads(metadata_file.read_text())
        assert "1.2.3" in metadata["versions"]
        assert metadata["versions"]["1.2.3"]["filename"] == f"{app_name}-1.2.3.AppImage"

    @pytest.mark.asyncio
    async def test_create_backup_app_not_installed(self, backup_handler, mock_config_manager):
        """Test backup creation for non-installed app."""
        mock_config_manager.load_app_config.return_value = None

        args = MagicMock()
        args.app_name = "nonexistent"
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = False
        args.migrate = False

        # Execute - should handle gracefully
        await backup_handler.execute(args)

        # Verify config was checked
        mock_config_manager.load_app_config.assert_called_with("nonexistent")

    @pytest.mark.asyncio
    async def test_restore_last_success(
        self, backup_handler, mock_config_manager, sample_app_config, temp_config
    ):
        """Test successful restore of latest backup."""
        global_config, backup_dir, storage_dir = temp_config

        # Setup - create a backup first
        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backup file and metadata
        backup_file = app_backup_dir / f"{app_name}-1.2.2.AppImage"
        backup_file.write_text("backup content")

        # Use BackupMetadata to create proper checksums
        from my_unicorn.backup import BackupMetadata

        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version("1.2.2", f"{app_name}-1.2.2.AppImage", backup_file)

        # Mock config manager
        mock_config_manager.load_app_config.return_value = sample_app_config

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = True
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = False
        args.migrate = False

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
        self, backup_handler, mock_config_manager, sample_app_config, temp_config
    ):
        """Test restoring a specific version."""
        global_config, backup_dir, storage_dir = temp_config

        app_name = "appflowy"
        version = "1.2.1"

        # Setup backup
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        backup_file = app_backup_dir / f"{app_name}-{version}.AppImage"
        backup_file.write_text("specific version content")

        # Use BackupMetadata to create proper checksums
        from my_unicorn.backup import BackupMetadata

        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version(version, f"{app_name}-{version}.AppImage", backup_file)

        mock_config_manager.load_app_config.return_value = sample_app_config

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = version
        args.list_backups = False
        args.cleanup = False
        args.info = False
        args.migrate = False

        await backup_handler.execute(args)

        # Verify specific version was restored
        restored_file = storage_dir / "appflowy.AppImage"
        assert restored_file.exists()
        assert restored_file.read_text() == "specific version content"

    @pytest.mark.asyncio
    async def test_list_backups_for_app(
        self, backup_handler, mock_config_manager, temp_config
    ):
        """Test listing backups for a specific app."""
        global_config, backup_dir, storage_dir = temp_config

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create multiple backup versions using BackupMetadata for proper checksums
        from my_unicorn.backup import BackupMetadata

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
        args.migrate = False

        # Execute and verify no exceptions
        await backup_handler.execute(args)

        # Verify the backups were properly listed by checking metadata
        metadata = metadata_manager.load()
        assert len(metadata["versions"]) == 3
        assert all(v in metadata["versions"] for v in versions)

    @pytest.mark.asyncio
    async def test_list_backups_for_nonexistent_app(self, backup_handler, mock_config_manager):
        """Test listing backups for a non-existent app."""
        args = MagicMock()
        args.app_name = "nonexistentapp"
        args.restore_last = False
        args.restore_version = None
        args.list_backups = True
        args.cleanup = False
        args.info = False
        args.migrate = False

        # Should execute without error even if app has no backups
        await backup_handler.execute(args)

    @pytest.mark.asyncio
    async def test_list_backups_requires_app_name(self, backup_handler):
        """Test that --list-backups requires app_name."""
        args = MagicMock()
        args.app_name = None
        args.restore_last = False
        args.restore_version = None
        args.list_backups = True
        args.cleanup = False
        args.info = False
        args.migrate = False

        # Should fail validation
        result = backup_handler._validate_arguments(args)
        assert result is False

    @pytest.mark.asyncio
    async def test_info_command_with_backups(
        self, backup_handler, mock_config_manager, temp_config
    ):
        """Test --info command shows detailed backup information."""
        global_config, backup_dir, storage_dir = temp_config

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backups using BackupMetadata for proper structure
        from my_unicorn.backup import BackupMetadata

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
        args.migrate = False

        # Execute and verify no exceptions
        await backup_handler.execute(args)

        # Verify backup info is accessible
        backup_info = backup_handler.backup_service.get_backup_info(app_name)
        assert len(backup_info) == 3
        assert all(info["version"] in versions for info in backup_info)

    @pytest.mark.asyncio
    async def test_info_command_no_backups(self, backup_handler, mock_config_manager):
        """Test --info command when app has no backups."""
        args = MagicMock()
        args.app_name = "appwithnobackups"
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True
        args.migrate = False

        # Should execute without error even if no backups exist
        await backup_handler.execute(args)

    @pytest.mark.asyncio
    async def test_info_requires_app_name(self, backup_handler):
        """Test that --info requires app_name."""
        args = MagicMock()
        args.app_name = None
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True
        args.migrate = False

        # Should fail validation
        result = backup_handler._validate_arguments(args)
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_backups_specific_app(
        self, backup_handler, mock_config_manager, temp_config
    ):
        """Test cleanup of old backups for a specific app."""
        global_config, backup_dir, storage_dir = temp_config
        global_config["max_backup"] = 2

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create multiple backup versions using BackupMetadata
        from my_unicorn.backup import BackupMetadata

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
        args.migrate = False

        await backup_handler.execute(args)

        # Should keep only max_backup (2) files
        remaining_files = list(app_backup_dir.glob("*.AppImage"))
        assert len(remaining_files) <= 2

        # Verify metadata was updated
        updated_metadata = metadata_manager.load()
        assert len(updated_metadata["versions"]) <= 2

    @pytest.mark.asyncio
    async def test_cleanup_backups_global(
        self, backup_handler, mock_config_manager, temp_config
    ):
        """Test cleanup of old backups for all apps."""
        global_config, backup_dir, storage_dir = temp_config
        global_config["max_backup"] = 1

        # Create backup directories for multiple apps
        apps = ["appflowy", "obsidian"]
        from my_unicorn.backup import BackupMetadata

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
        args.migrate = False

        await backup_handler.execute(args)

        # Each app should have only max_backup (1) files
        for app_name in apps:
            app_backup_dir = backup_dir / app_name
            remaining_files = list(app_backup_dir.glob("*.AppImage"))
            assert len(remaining_files) <= 1

    @pytest.mark.asyncio
    async def test_cleanup_zero_max_backup(
        self, backup_handler, mock_config_manager, temp_config
    ):
        """Test cleanup when max_backup is set to 0 (remove all)."""
        global_config, backup_dir, storage_dir = temp_config
        global_config["max_backup"] = 0

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backups using BackupMetadata
        from my_unicorn.backup import BackupMetadata

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
        args.migrate = False

        await backup_handler.execute(args)

        # All backups should be removed
        remaining_files = list(app_backup_dir.glob("*.AppImage"))
        assert len(remaining_files) == 0

        # Metadata file should also be removed
        assert not (app_backup_dir / "metadata.json").exists()

    @pytest.mark.asyncio
    async def test_show_backup_info(self, backup_handler, mock_config_manager, temp_config):
        """Test showing backup information."""
        global_config, backup_dir, storage_dir = temp_config

        app_name = "appflowy"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        # Create backup with metadata
        backup_file = app_backup_dir / f"{app_name}-1.2.3.AppImage"
        backup_file.write_text("backup content")

        metadata = {
            "versions": {
                "1.2.3": {
                    "filename": f"{app_name}-1.2.3.AppImage",
                    "sha256": "backup_hash",
                    "created": datetime.now().isoformat(),
                    "size": len("backup content"),
                }
            }
        }
        metadata_file = app_backup_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True
        args.migrate = False

        await backup_handler.execute(args)

    @pytest.mark.asyncio
    async def test_migrate_old_backups(self, backup_handler, mock_config_manager, temp_config):
        """Test migration of old backup format."""
        global_config, backup_dir, storage_dir = temp_config

        # Create old format backup files
        old_backups = [
            "freetube-0.23.6.backup.AppImage",
            "appflowy-1.2.3.backup.AppImage",
            "obsidian-1.4.14.backup.AppImage",
        ]

        for old_backup_name in old_backups:
            old_backup_path = backup_dir / old_backup_name
            old_backup_path.write_text(f"content of {old_backup_name}")

        # Mock installed apps to help with parsing
        mock_config_manager.list_installed_apps.return_value = [
            "freetube",
            "appflowy",
            "obsidian",
        ]

        args = MagicMock()
        args.app_name = None
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = False
        args.migrate = True

        await backup_handler.execute(args)

        # Verify new folder structure was created
        expected_apps = ["freetube", "appflowy", "obsidian"]
        for app_name in expected_apps:
            app_backup_dir = backup_dir / app_name
            assert app_backup_dir.exists()
            assert (app_backup_dir / "metadata.json").exists()

        # Verify old files were removed
        for old_backup_name in old_backups:
            assert not (backup_dir / old_backup_name).exists()

    @pytest.mark.asyncio
    async def test_validate_arguments_missing_app_name(self, backup_handler):
        """Test argument validation when app_name is missing."""
        args = MagicMock()
        args.app_name = None
        args.restore_last = True
        args.migrate = False
        args.list_backups = False
        args.cleanup = False

        # Should fail validation
        result = backup_handler._validate_arguments(args)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_arguments_global_operations_no_app_name(self, backup_handler):
        """Test argument validation for global operations that don't need app_name."""
        # Test migrate
        args = MagicMock()
        args.app_name = None
        args.migrate = True
        args.list_backups = False
        args.cleanup = False

        result = backup_handler._validate_arguments(args)
        assert result is True

        # Test global cleanup
        args.migrate = False
        args.cleanup = True

        result = backup_handler._validate_arguments(args)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_arguments_invalid_app_name(self, backup_handler):
        """Test argument validation with invalid app name."""
        args = MagicMock()
        args.app_name = "app/with/slashes"
        args.restore_last = True
        args.migrate = False
        args.list_backups = False
        args.cleanup = False

        result = backup_handler._validate_arguments(args)
        assert result is False

    @pytest.mark.asyncio
    async def test_backup_current_version_before_restore(
        self, backup_handler, mock_config_manager, sample_app_config, temp_config
    ):
        """Test that current version is backed up before restore."""
        global_config, backup_dir, storage_dir = temp_config

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
        from my_unicorn.backup import BackupMetadata

        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version(
            restore_version, f"{app_name}-{restore_version}.AppImage", backup_file
        )

        # Mock config with different current version
        current_config = sample_app_config.copy()
        current_config["appimage"]["version"] = "1.2.3"  # Different from restore version

        mock_config_manager.load_app_config.return_value = current_config

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = restore_version
        args.list_backups = False
        args.cleanup = False
        args.info = False
        args.migrate = False

        await backup_handler.execute(args)

        # Verify current version was backed up
        metadata_manager = BackupMetadata(app_backup_dir)
        updated_metadata = metadata_manager.load()
        assert (
            "1.2.3" in updated_metadata["versions"]
        )  # Current version should now be in backups

        # Verify old version was restored
        assert current_appimage.read_text() == "old version content"

    def test_app_name_parsing_in_migration(self, mock_config_manager, temp_config):
        """Test that app names are parsed correctly during migration, especially for complex names like FreeTube."""
        global_config, backup_dir, storage_dir = temp_config
        backup_service = BackupService(mock_config_manager, global_config)

        # Create test cases that should be handled correctly
        test_cases = [
            ("freetube-0.23.6.backup.AppImage", "freetube", "0.23.6"),
            ("appflowy-1.2.3.backup.AppImage", "appflowy", "1.2.3"),
            ("my-app-2.1.0-beta.backup.AppImage", "my-app", "2.1.0-beta"),
            ("single.backup.AppImage", "single", "unknown"),
        ]

        # Mock installed apps to help with parsing
        mock_config_manager.list_installed_apps.return_value = [
            "freetube",
            "appflowy",
            "my-app",
            "single",
        ]

        # Create old backup files
        for filename, expected_app, expected_version in test_cases:
            old_backup_path = backup_dir / filename
            old_backup_path.write_text(f"content of {filename}")

        # Run migration
        migrated_count = backup_service.migrate_old_backups()

        # Verify correct parsing
        assert migrated_count == len(test_cases)

        # Verify correct parsing
        for filename, expected_app, expected_version in test_cases:
            app_backup_dir = backup_dir / expected_app
            assert app_backup_dir.exists(), f"Directory not created for {expected_app}"

            metadata_file = app_backup_dir / "metadata.json"
            assert metadata_file.exists(), f"Metadata not created for {expected_app}"

            metadata = json.loads(metadata_file.read_text())
            assert expected_version in metadata["versions"], (
                f"Version {expected_version} not found for {expected_app}"
            )

            # Verify old file was removed
            assert not (backup_dir / filename).exists(), f"Old file {filename} was not removed"

    def test_all_commands_require_app_name_except_global_operations(self, backup_handler):
        """Test that all commands except global operations require app_name."""
        # Commands that should require app_name
        required_app_name_commands = [
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
                assert result is False, f"Command {command_args} should require app_name"

        # Commands that don't require app_name (global operations)
        global_operations = [
            {"migrate": True},
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
            args.migrate = False

            # Set the specific command
            for key, value in command_args.items():
                setattr(args, key, value)

            result = backup_handler._validate_arguments(args)
            assert result is True, (
                f"Global operation {command_args} should not require app_name"
            )

    @pytest.mark.asyncio
    async def test_commands_produce_visible_output(
        self, backup_handler, mock_config_manager, temp_config, capsys
    ):
        """Test that commands produce visible output."""
        global_config, backup_dir, storage_dir = temp_config

        # Create test backup data
        app_name = "testapp"
        app_backup_dir = backup_dir / app_name
        app_backup_dir.mkdir(parents=True)

        from my_unicorn.backup import BackupMetadata

        backup_file = app_backup_dir / f"{app_name}-1.2.3.AppImage"
        backup_file.write_text("test content")

        metadata_manager = BackupMetadata(app_backup_dir)
        metadata_manager.add_version("1.2.3", f"{app_name}-1.2.3.AppImage", backup_file)

        # Test --info command output
        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True
        args.migrate = False

        await backup_handler.execute(args)
        captured = capsys.readouterr()

        assert "Backup Statistics for testapp" in captured.out
        assert "Total backups: 1" in captured.out
        assert "Configuration:" in captured.out

        # Test --list-backups command output
        args.info = False
        args.list_backups = True

        await backup_handler.execute(args)
        captured = capsys.readouterr()

        assert "Available backups for testapp" in captured.out
        assert "v1.2.3" in captured.out
        assert "SHA256:" in captured.out

        # Test --cleanup command output
        args.list_backups = False
        args.cleanup = True

        await backup_handler.execute(args)
        captured = capsys.readouterr()

        assert "Cleaning up old backups for testapp" in captured.out
        assert "Cleanup completed" in captured.out
