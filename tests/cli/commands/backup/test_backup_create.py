"""Tests for BackupHandler backup creation operations."""

from datetime import datetime
from unittest.mock import MagicMock

import orjson
import pytest

from my_unicorn.cli.commands.backup import BackupHandler


class TestBackupHandler:
    """Test BackupHandler backup creation operations."""

    @pytest.mark.asyncio
    async def test_create_backup_success(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        sample_app_config: dict,
        temp_config: tuple,
    ) -> None:
        """Test successful backup creation."""
        _, backup_dir, storage_dir = temp_config

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

        metadata = orjson.loads(metadata_file.read_bytes())
        assert "1.2.3" in metadata["versions"]
        assert (
            metadata["versions"]["1.2.3"]["filename"]
            == f"{app_name}-1.2.3.AppImage"
        )

    @pytest.mark.asyncio
    async def test_create_backup_app_not_installed(
        self, backup_handler: BackupHandler, mock_config_manager: MagicMock
    ) -> None:
        """Test backup creation for non-installed app."""
        mock_config_manager.load_app_config.return_value = None

        args = MagicMock()
        args.app_name = "nonexistent"
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = False

        # Execute - should handle gracefully
        await backup_handler.execute(args)

        # Verify config was checked
        mock_config_manager.load_app_config.assert_called_with("nonexistent")

    @pytest.mark.asyncio
    async def test_show_backup_info(
        self,
        backup_handler: BackupHandler,
        mock_config_manager: MagicMock,
        temp_config: tuple,
    ) -> None:
        """Test showing backup information."""
        _, backup_dir, _ = temp_config

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
                    "created": datetime.now().astimezone().isoformat(),
                    "size": len("backup content"),
                }
            }
        }
        metadata_file = app_backup_dir / "metadata.json"
        metadata_file.write_bytes(orjson.dumps(metadata))

        args = MagicMock()
        args.app_name = app_name
        args.restore_last = False
        args.restore_version = None
        args.list_backups = False
        args.cleanup = False
        args.info = True

        await backup_handler.execute(args)
