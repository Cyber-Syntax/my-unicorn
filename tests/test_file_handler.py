#!/usr/bin/env python3
"""Tests for the file handler module.

This module contains pytest tests for the FileHandler class, which handles
AppImage file operations, desktop entry creation, and backup management.
"""

import shutil
import stat
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.file_handler import FileHandler
from my_unicorn.global_config import GlobalConfigManager


@pytest.fixture
def mock_global_config(monkeypatch, temp_dirs):
    """Mock GlobalConfigManager for testing FileHandler.

    Args:
        monkeypatch: pytest monkeypatch fixture
        temp_dirs: Temporary directories fixture

    Returns:
        MagicMock: Configured mock GlobalConfigManager

    """
    mock_config = MagicMock(spec=GlobalConfigManager)
    mock_config.expanded_app_download_path = str(temp_dirs["downloads_dir"])

    # Mock the GlobalConfigManager's constructor to return our mock
    def mock_gc_init():
        return mock_config

    monkeypatch.setattr("my_unicorn.file_handler.GlobalConfigManager", mock_gc_init)
    return mock_config


@pytest.fixture
def temp_dirs(tmp_path: Path) -> tuple[str, Path]:
    """Create temporary directories for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        tuple[str, Path]: Dictionary of test directories

    """
    app_dir = tmp_path / "apps"
    backup_dir = tmp_path / "backups"
    downloads_dir = tmp_path / "downloads"

    for directory in [app_dir, backup_dir, downloads_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return {"app_dir": app_dir, "backup_dir": backup_dir, "downloads_dir": downloads_dir}


@pytest.fixture
def file_handler(temp_dirs: tuple[str, Path]) -> FileHandler:
    """Create a FileHandler instance for testing.

    Args:
        temp_dirs: Dictionary of test directories

    Returns:
        FileHandler: Configured FileHandler instance

    """
    return FileHandler(
        appimage_name="test-app.AppImage",
        repo="test-app",
        owner="test-owner",
        version="1.0.0",
        checksum_file_name="sha256sums",
        app_storage_path=str(temp_dirs["app_dir"]),
        app_backup_storage_path=str(temp_dirs["backup_dir"]),
        config_folder=str(temp_dirs["app_dir"]),
        config_file_name="test-app.json",
        batch_mode=True,
    )


@pytest.fixture
def mock_appimage(temp_dirs: tuple[str, Path]) -> Path:
    """Create a mock AppImage file for testing.

    Args:
        temp_dirs: Dictionary of test directories

    Returns:
        Path: Path to the mock AppImage file

    """
    # Create app directory
    app_path = temp_dirs["app_dir"] / "test-app.AppImage"
    app_path.write_bytes(b"MockAppImageContent")

    # Create download directory file
    download_path = temp_dirs["downloads_dir"] / "test-app.AppImage"
    download_path.write_bytes(b"MockDownloadedAppImageContent")

    return app_path


class TestFileHandler:
    """Tests for the FileHandler class."""

    def test_initialization(self, file_handler: FileHandler) -> None:
        """Test FileHandler initialization with default parameters.

        Args:
            file_handler: FileHandler fixture

        """
        assert file_handler.appimage_name == "test-app.AppImage"
        assert file_handler.repo == "test-app"
        assert file_handler.owner == "test-owner"
        assert file_handler.version == "1.0.0"
        assert file_handler.checksum_file_name == "sha256sums"
        assert file_handler.batch_mode is True
        assert file_handler.keep_backup is True
        assert file_handler.max_backups == 3
        assert isinstance(file_handler.app_storage_path, Path)
        assert isinstance(file_handler.app_backup_storage_path, Path)
        assert isinstance(file_handler.installed_path, Path)
        assert isinstance(file_handler.download_path, Path)

    def test_initialization_with_empty_params(self) -> None:
        """Test FileHandler initialization validation with empty parameters."""
        with pytest.raises(ValueError, match="AppImage name cannot be empty"):
            FileHandler(appimage_name="", repo="test-app")

        with pytest.raises(ValueError, match="Repository name cannot be empty"):
            FileHandler(appimage_name="test-app.AppImage", repo="")

    def test_ensure_directories_exist(self, file_handler: FileHandler) -> None:
        """Test directory creation.

        Args:
            file_handler: FileHandler fixture

        """
        # Remove directories to test creation
        if file_handler.app_storage_path.exists():
            shutil.rmtree(file_handler.app_storage_path)
        if file_handler.app_backup_storage_path.exists():
            shutil.rmtree(file_handler.app_backup_storage_path)

        file_handler._ensure_directories_exist()

        assert file_handler.app_storage_path.exists()
        assert file_handler.app_backup_storage_path.exists()

    def test_backup_appimage(
        self, file_handler: FileHandler, mock_appimage: Path, temp_dirs: tuple[str, Path]
    ) -> None:
        """Test AppImage backup functionality.

        Args:
            file_handler: FileHandler fixture
            mock_appimage: Path to mock AppImage file
            temp_dirs: Dictionary of test directories

        """
        # Ensure the file exists at installed_path location
        assert file_handler.installed_path.exists()

        # Test backup creation
        success = file_handler._backup_appimage()
        assert success is True

        # Check that a backup was created (should be the only file in backup dir with .AppImage extension)
        backup_files = list(temp_dirs["backup_dir"].glob("*.AppImage"))
        assert len(backup_files) == 1
        assert backup_files[0].name.startswith("test-app_")
        assert backup_files[0].name.endswith(".AppImage")

        # Test backup with keep_backup=False
        file_handler.keep_backup = False
        success = file_handler._backup_appimage()
        assert success is True
        # No new backups should be created
        assert len(list(temp_dirs["backup_dir"].glob("*.AppImage"))) == 1

    def test_cleanup_old_backups(
        self, file_handler: FileHandler, temp_dirs: tuple[str, Path]
    ) -> None:
        """Test cleanup of old backup files.

        Args:
            file_handler: FileHandler fixture
            temp_dirs: Dictionary of test directories

        """
        backup_dir = temp_dirs["backup_dir"]

        # Create more backup files than max_backups
        for i in range(5):  # Create 5 backup files (max is 3)
            timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(time.time() - i * 1000))
            backup_file = backup_dir / f"test-app_{timestamp}.AppImage"
            backup_file.write_bytes(b"MockBackupContent")
            # Ensure each file has a different modification time
            backup_file.touch(exist_ok=True)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Run cleanup
        file_handler._cleanup_old_backups("test-app")

        # Should have max_backups files now
        backup_files = list(backup_dir.glob("*.AppImage"))
        assert len(backup_files) == file_handler.max_backups

        # The newest files should be kept
        for backup_file in backup_files:
            assert backup_file.name.startswith("test-app_")

    def test_move_appimage(self, file_handler: FileHandler, temp_dirs: tuple[str, Path]) -> None:
        """Test moving an AppImage file from downloads to the app directory.

        Args:
            file_handler: FileHandler fixture
            temp_dirs: Dictionary of test directories

        """
        # Create source file in downloads dir
        downloaded_file = temp_dirs["downloads_dir"] / file_handler.appimage_name
        downloaded_file.write_bytes(b"DownloadedAppImageContent")

        # Patch the GlobalConfigManager class in its own module
        with patch("my_unicorn.global_config.GlobalConfigManager") as MockGlobalConfigClass:
            # Configure the mock instance that will be returned when the class is instantiated
            mock_gc_instance = MagicMock()
            mock_gc_instance.expanded_app_download_path = str(temp_dirs["downloads_dir"])
            MockGlobalConfigClass.return_value = mock_gc_instance

            # Test move
            success = file_handler._move_appimage()
            assert success is True

            # Check source file is gone
            assert not downloaded_file.exists()

            # Check destination file exists
            assert file_handler.installed_path.exists()
            assert file_handler.installed_path.read_bytes() == b"DownloadedAppImageContent"

    def test_move_appimage_source_not_found(
        self, file_handler: FileHandler, temp_dirs: tuple[str, Path]
    ) -> None:
        """Test moving an AppImage file when the source file doesn't exist.

        Args:
            file_handler: FileHandler fixture
            temp_dirs: Dictionary of test directories

        """
        # No source file, should fail
        downloaded_file = temp_dirs["downloads_dir"] / file_handler.appimage_name
        if downloaded_file.exists():
            downloaded_file.unlink()

        # Patch the GlobalConfigManager class
        with patch("my_unicorn.global_config.GlobalConfigManager") as MockGlobalConfigClass:
            # Configure the mock instance
            mock_gc_instance = MagicMock()
            mock_gc_instance.expanded_app_download_path = str(temp_dirs["downloads_dir"])
            MockGlobalConfigClass.return_value = mock_gc_instance

            success = file_handler._move_appimage()
            assert success is False

    def test_set_executable_permission(
        self, file_handler: FileHandler, mock_appimage: Path
    ) -> None:
        """Test setting executable permissions on an AppImage.

        Args:
            file_handler: FileHandler fixture
            mock_appimage: Path to mock AppImage file

        """
        # Remove executable permission first
        mock_appimage.chmod(0o644)

        # Test setting permission
        success = file_handler._set_executable_permission()
        assert success is True

        # Check permission was set
        st_mode = file_handler.installed_path.stat().st_mode
        assert bool(st_mode & stat.S_IXUSR)
        assert bool(st_mode & stat.S_IXGRP)
        assert bool(st_mode & stat.S_IXOTH)

    def test_handle_appimage_operations(
        self,
        file_handler: FileHandler,
        mock_appimage: Path,
        temp_dirs: tuple[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test the main handle_appimage_operations method.

        Args:
            file_handler: FileHandler fixture
            mock_appimage: Path to mock AppImage file
            temp_dirs: Dictionary of test directories
            monkeypatch: pytest monkeypatch fixture

        """
        # Mock dependencies
        monkeypatch.setattr(
            "my_unicorn.file_handler.DESKTOP_ENTRY_DIR",
            Path(file_handler.app_storage_path) / "applications",
        )

        # Mock the individual operations
        with patch.object(file_handler, "_ensure_directories_exist") as mock_ensure_dirs:
            with patch.object(file_handler, "_backup_appimage", return_value=True) as mock_backup:
                with patch.object(file_handler, "_move_appimage", return_value=True) as mock_move:
                    with patch.object(
                        file_handler, "_set_executable_permission", return_value=True
                    ) as mock_set_perm:
                        with patch.object(
                            file_handler, "_create_desktop_entry", return_value=True
                        ) as mock_create_desktop:
                            # Run the operation
                            success = file_handler.handle_appimage_operations()

                            # Check result
                            assert success is True

                            # Verify all operations were called
                            mock_ensure_dirs.assert_called_once()
                            mock_backup.assert_called_once()
                            mock_move.assert_called_once()
                            mock_set_perm.assert_called_once()
                            mock_create_desktop.assert_called_once()

    def test_handle_appimage_operations_with_failures(self, file_handler: FileHandler) -> None:
        """Test handle_appimage_operations with failures in the process.

        Args:
            file_handler: FileHandler fixture

        """
        # Mock individual operations with one failing
        with patch.object(file_handler, "_ensure_directories_exist"):
            with patch.object(file_handler, "_backup_appimage", return_value=True):
                with patch.object(
                    file_handler, "_move_appimage", return_value=False
                ):  # This one fails
                    # Run the operation
                    success = file_handler.handle_appimage_operations()

                    # Check result - should fail when move fails
                    assert success is False
