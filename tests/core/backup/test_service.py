"""Tests for BackupService.

Tests for backup creation, cleanup, listing, and info retrieval operations.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import orjson

from my_unicorn.core.backup import BackupMetadata


class TestBackupServiceCreate:
    """Test BackupService backup creation functionality."""

    def test_create_backup_with_folder_structure(
        self,
        backup_service: Any,
        dummy_config: Any,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test backup creation with new folder structure."""
        config_manager, _, _, storage_dir = dummy_config
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

    def test_create_backup_missing_file(self, backup_service: Any) -> None:
        """Test backup creation with missing source file."""
        file_path = Path("nonexistent.AppImage")
        backup = backup_service.create_backup(file_path, "app1")
        assert backup is None


class TestBackupServiceCleanup:
    """Test BackupService cleanup functionality."""

    def test_cleanup_old_backups_folder_structure(
        self,
        backup_service: Any,
        dummy_config: Any,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test cleanup with new folder structure."""
        _, global_config, backup_dir, _ = dummy_config
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
            timestamp = datetime.now(UTC) - timedelta(
                days=len(versions) - i - 1
            )
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

    def test_cleanup_max_zero_removes_all(
        self, backup_service: Any, dummy_config: Any
    ) -> None:
        """Test that max_backup=0 removes all backups."""
        _, global_config, backup_dir, _ = dummy_config
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


class TestBackupServiceInfo:
    """Test BackupService info and listing functionality."""

    def test_get_backup_info_with_metadata(
        self, backup_service: Any, dummy_config: Any
    ) -> None:
        """Test getting backup info from metadata."""
        _, _, backup_dir, _ = dummy_config

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

    def test_list_apps_with_backups(
        self, backup_service: Any, dummy_config: Any
    ) -> None:
        """Test listing apps that have backups."""
        _, _, backup_dir, _ = dummy_config

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
