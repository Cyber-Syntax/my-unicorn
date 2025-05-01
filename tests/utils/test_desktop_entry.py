#!/usr/bin/env python3
"""Tests for desktop entry utility functions.

This module contains tests for the desktop entry management functionality in
src/utils/desktop_entry.py used for creating and updating desktop entries for
AppImage applications.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.desktop_entry import (
    DEFAULT_CATEGORIES,
    DESKTOP_ENTRY_DIR,
    DESKTOP_ENTRY_FILE_MODE,
    DESKTOP_FILE_SECTION,
    DesktopEntryManager,
)


class TestDesktopEntryManager:
    """Tests for DesktopEntryManager class."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory for desktop entry files.

        Args:
            tmp_path: Pytest fixture that provides a temporary directory path

        Returns:
            Path to the temporary directory

        """
        desktop_dir = tmp_path / "applications"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        return desktop_dir

    @pytest.fixture
    def desktop_manager(self, temp_dir: Path) -> DesktopEntryManager:
        """Create a DesktopEntryManager instance with a temporary directory.

        Args:
            temp_dir: Path to the temporary directory

        Returns:
            DesktopEntryManager instance

        """
        return DesktopEntryManager(desktop_dir=temp_dir)

    def test_initialization(self, temp_dir: Path) -> None:
        """Test initialization of DesktopEntryManager.

        Args:
            temp_dir: Path to the temporary directory

        """
        desktop_manager = DesktopEntryManager(desktop_dir=temp_dir)

        assert desktop_manager.desktop_dir == temp_dir
        assert temp_dir.exists()
        assert temp_dir.is_dir()

    def test_initialization_default_dir(self) -> None:
        """Test initialization with default desktop directory."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            desktop_manager = DesktopEntryManager()

            assert desktop_manager.desktop_dir == DESKTOP_ENTRY_DIR
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_read_desktop_file_nonexistent(self, desktop_manager: DesktopEntryManager) -> None:
        """Test reading a nonexistent desktop file.

        Args:
            desktop_manager: DesktopEntryManager instance

        """
        nonexistent_path = desktop_manager.desktop_dir / "nonexistent.desktop"

        entries = desktop_manager.read_desktop_file(nonexistent_path)

        assert entries == {}

    def test_read_desktop_file_valid(
        self, desktop_manager: DesktopEntryManager, temp_dir: Path
    ) -> None:
        """Test reading a valid desktop file.

        Args:
            desktop_manager: DesktopEntryManager instance
            temp_dir: Path to the temporary directory

        """
        desktop_path = temp_dir / "testapp.desktop"
        file_content = """
[Desktop Entry]
Type=Application
Name=TestApp
Exec=/path/to/TestApp.AppImage
Terminal=false
Categories=Utility;
Comment=AppImage for TestApp
Icon=/path/to/icon.png

[Other Section]
Key=Value
"""
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        entries = desktop_manager.read_desktop_file(desktop_path)

        assert entries == {
            "Type": "Application",
            "Name": "TestApp",
            "Exec": "/path/to/TestApp.AppImage",
            "Terminal": "false",
            "Categories": "Utility;",
            "Comment": "AppImage for TestApp",
            "Icon": "/path/to/icon.png",
        }

    def test_read_desktop_file_os_error(self, desktop_manager: DesktopEntryManager) -> None:
        """Test reading a desktop file with OS error.

        Args:
            desktop_manager: DesktopEntryManager instance

        """
        desktop_path = Path("/nonexistent/directory/file.desktop")

        with patch("logging.Logger.warning") as mock_warning:
            entries = desktop_manager.read_desktop_file(desktop_path)

            assert entries == {}
            assert mock_warning.call_count == 1
            assert "OS error" in mock_warning.call_args[0][0]

    def test_needs_update_no_change(self) -> None:
        """Test needs_update when no change is needed."""
        desktop_manager = DesktopEntryManager()

        existing_entries = {
            "Type": "Application",
            "Name": "TestApp",
            "Exec": "/path/to/TestApp.AppImage",
        }

        new_entries = existing_entries.copy()

        assert desktop_manager.needs_update(existing_entries, new_entries) is False

    def test_needs_update_value_changed(self) -> None:
        """Test needs_update when a value has changed."""
        desktop_manager = DesktopEntryManager()

        existing_entries = {
            "Type": "Application",
            "Name": "TestApp",
            "Exec": "/path/to/TestApp.AppImage",
        }

        new_entries = existing_entries.copy()
        new_entries["Exec"] = "/path/to/updated/TestApp.AppImage"

        with patch("logging.Logger.info") as mock_info:
            assert desktop_manager.needs_update(existing_entries, new_entries) is True
            mock_info.assert_called_once()
            assert "changed" in mock_info.call_args[0][0]

    def test_needs_update_new_key(self) -> None:
        """Test needs_update when a new key is added."""
        desktop_manager = DesktopEntryManager()

        existing_entries = {
            "Type": "Application",
            "Name": "TestApp",
            "Exec": "/path/to/TestApp.AppImage",
        }

        new_entries = existing_entries.copy()
        new_entries["Icon"] = "/path/to/icon.png"

        assert desktop_manager.needs_update(existing_entries, new_entries) is True

    def test_write_desktop_file_success(
        self, desktop_manager: DesktopEntryManager, temp_dir: Path
    ) -> None:
        """Test writing a desktop file successfully.

        Args:
            desktop_manager: DesktopEntryManager instance
            temp_dir: Path to the temporary directory

        """
        desktop_path = temp_dir / "testapp.desktop"

        new_entries = {
            "Type": "Application",
            "Name": "TestApp",
            "Exec": "/path/to/TestApp.AppImage",
            "Terminal": "false",
            "Categories": "Utility;",
            "Comment": "AppImage for TestApp",
        }

        existing_entries = {
            "CustomKey": "CustomValue",
        }

        result = desktop_manager.write_desktop_file(desktop_path, new_entries, existing_entries)

        assert result is True
        assert desktop_path.exists()
        assert desktop_path.is_file()

        # Check file contents
        with open(desktop_path, encoding="utf-8") as f:
            content = f.read()
            assert f"[{DESKTOP_FILE_SECTION}]" in content
            for key, value in new_entries.items():
                assert f"{key}={value}" in content
            for key, value in existing_entries.items():
                assert f"{key}={value}" in content

        # Check file permissions
        file_mode = desktop_path.stat().st_mode
        assert file_mode & DESKTOP_ENTRY_FILE_MODE == DESKTOP_ENTRY_FILE_MODE

    def test_write_desktop_file_cleanup_on_error(
        self, desktop_manager: DesktopEntryManager, temp_dir: Path
    ) -> None:
        """Test cleanup of temporary file when write fails.

        Args:
            desktop_manager: DesktopEntryManager instance
            temp_dir: Path to the temporary directory

        """
        desktop_path = temp_dir / "testapp.desktop"
        temp_path = desktop_path.with_suffix(".tmp")

        # Create a temp file to ensure it gets cleaned up
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write("Test content")

        # Make replace throw an exception
        with patch("pathlib.Path.replace", side_effect=OSError("Test error")):
            with patch("logging.Logger.error") as mock_error:
                with patch("logging.Logger.warning") as mock_warning:
                    result = desktop_manager.write_desktop_file(
                        desktop_path, {"Type": "Application"}, {}
                    )

                    assert result is False
                    mock_error.assert_called_once()
                    assert not temp_path.exists()  # Temp file should be cleaned up

    def test_create_or_update_desktop_entry_empty_app_display_name(
        self, desktop_manager: DesktopEntryManager
    ) -> None:
        """Test create_or_update_desktop_entry with empty app_display_name.

        Args:
            desktop_manager: DesktopEntryManager instance

        """
        success, message = desktop_manager.create_or_update_desktop_entry(
            app_display_name="", appimage_path="/path/to/app.AppImage"
        )

        assert success is False
        assert "identifier cannot be empty" in message

    def test_create_or_update_desktop_entry_new_file(
        self, desktop_manager: DesktopEntryManager, temp_dir: Path
    ) -> None:
        """Test create_or_update_desktop_entry for a new desktop entry file.

        Args:
            desktop_manager: DesktopEntryManager instance
            temp_dir: Path to the temporary directory

        """
        app_display_name = "TestApp"
        appimage_path = "/path/to/TestApp.AppImage"
        icon_path = "/path/to/icon.png"

        desktop_path = temp_dir / f"{app_display_name.lower()}.desktop"

        with patch("logging.Logger.info") as mock_info:
            success, message = desktop_manager.create_or_update_desktop_entry(
                app_display_name=app_display_name, appimage_path=appimage_path, icon_path=icon_path
            )

            assert success is True
            assert str(desktop_path) == message
            assert desktop_path.exists()
            assert desktop_path.is_file()

            # Verify log messages
            assert any("Using icon from" in call[0][0] for call in mock_info.call_args_list)

            # Check file contents
            with open(desktop_path, encoding="utf-8") as f:
                content = f.read()
                assert f"[{DESKTOP_FILE_SECTION}]" in content
                assert "Type=Application" in content
                assert f"Name={app_display_name}" in content
                assert f"Exec={appimage_path}" in content
                assert "Terminal=false" in content
                assert f"Categories={DEFAULT_CATEGORIES}" in content
                assert f"Comment=AppImage for {app_display_name}" in content
                assert f"Icon={icon_path}" in content

    def test_create_or_update_desktop_entry_update(
        self, desktop_manager: DesktopEntryManager, temp_dir: Path
    ) -> None:
        """Test create_or_update_desktop_entry to update existing file.

        Args:
            desktop_manager: DesktopEntryManager instance
            temp_dir: Path to the temporary directory

        """
        app_display_name = "TestApp"
        old_appimage_path = "/path/to/TestApp.AppImage"
        new_appimage_path = "/path/to/updated/TestApp.AppImage"

        # Create existing desktop file
        desktop_path = temp_dir / f"{app_display_name.lower()}.desktop"
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(f"""[Desktop Entry]
Type=Application
Name={app_display_name}
Exec={old_appimage_path}
Terminal=false
Categories={DEFAULT_CATEGORIES}
Comment=AppImage for {app_display_name}
CustomKey=CustomValue
""")

        # Update the desktop file
        success, message = desktop_manager.create_or_update_desktop_entry(
            app_display_name=app_display_name, appimage_path=new_appimage_path
        )

        assert success is True
        assert str(desktop_path) == message

        # Check file was updated
        with open(desktop_path, encoding="utf-8") as f:
            content = f.read()
            assert f"Exec={new_appimage_path}" in content
            assert "CustomKey=CustomValue" in content  # Preserved from original

    def test_create_or_update_desktop_entry_no_update_needed(
        self, desktop_manager: DesktopEntryManager, temp_dir: Path
    ) -> None:
        """Test create_or_update_desktop_entry when no update is needed.

        Args:
            desktop_manager: DesktopEntryManager instance
            temp_dir: Path to the temporary directory

        """
        app_display_name = "TestApp"
        appimage_path = "/path/to/TestApp.AppImage"

        # Create existing desktop file
        desktop_path = temp_dir / f"{app_display_name.lower()}.desktop"
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(f"""[Desktop Entry]
Type=Application
Name={app_display_name}
Exec={appimage_path}
Terminal=false
Categories={DEFAULT_CATEGORIES}
Comment=AppImage for {app_display_name}
""")

        # Try to update with same values
        with patch.object(
            desktop_manager, "write_desktop_file", wraps=desktop_manager.write_desktop_file
        ) as mock_write:
            success, message = desktop_manager.create_or_update_desktop_entry(
                app_display_name=app_display_name, appimage_path=appimage_path
            )

            assert success is True
            assert str(desktop_path) == message

            # write_desktop_file should not be called since no update is needed
            mock_write.assert_not_called()

    def test_create_or_update_desktop_entry_with_path_objects(
        self, desktop_manager: DesktopEntryManager
    ) -> None:
        """Test create_or_update_desktop_entry with Path objects.

        Args:
            desktop_manager: DesktopEntryManager instance

        """
        app_display_name = "TestApp"
        appimage_path = Path("/path/to/TestApp.AppImage")
        icon_path = Path("/path/to/icon.png")

        with patch.object(desktop_manager, "write_desktop_file", return_value=True) as mock_write:
            with patch.object(desktop_manager, "read_desktop_file", return_value={}):
                success, _ = desktop_manager.create_or_update_desktop_entry(
                    app_display_name=app_display_name,
                    appimage_path=appimage_path,
                    icon_path=icon_path,
                )

                assert success is True

                # Check the paths were converted correctly
                # Extract the new_entries argument from the write_desktop_file call
                call_args = mock_write.call_args[0]
                new_entries = call_args[1]

                assert new_entries["Exec"] == str(appimage_path)
                assert new_entries["Icon"] == str(icon_path)

    def test_create_or_update_desktop_entry_no_icon(
        self, desktop_manager: DesktopEntryManager, temp_dir: Path
    ) -> None:
        """Test create_or_update_desktop_entry with no icon.

        Args:
            desktop_manager: DesktopEntryManager instance
            temp_dir: Path to the temporary directory

        """
        app_display_name = "TestApp"
        appimage_path = "/path/to/TestApp.AppImage"

        with patch("logging.Logger.info") as mock_info:
            success, _ = desktop_manager.create_or_update_desktop_entry(
                app_display_name=app_display_name, appimage_path=appimage_path
            )

            assert success is True

            # Verify log message about no icon
            assert any("No icon specified" in call[0][0] for call in mock_info.call_args_list)

    def test_create_or_update_desktop_entry_write_failure(
        self, desktop_manager: DesktopEntryManager
    ) -> None:
        """Test create_or_update_desktop_entry when write fails.

        Args:
            desktop_manager: DesktopEntryManager instance

        """
        app_display_name = "TestApp"
        appimage_path = "/path/to/TestApp.AppImage"

        with patch.object(desktop_manager, "write_desktop_file", return_value=False):
            success, message = desktop_manager.create_or_update_desktop_entry(
                app_display_name=app_display_name, appimage_path=appimage_path
            )

            assert success is False
            assert "Failed to write desktop entry" in message

    def test_create_or_update_desktop_entry_fs_error(
        self, desktop_manager: DesktopEntryManager
    ) -> None:
        """Test create_or_update_desktop_entry with filesystem error.

        Args:
            desktop_manager: DesktopEntryManager instance

        """
        app_display_name = "TestApp"
        appimage_path = "/path/to/TestApp.AppImage"

        with patch.object(desktop_manager, "read_desktop_file", side_effect=OSError("Test error")):
            with patch("logging.Logger.error") as mock_error:
                success, message = desktop_manager.create_or_update_desktop_entry(
                    app_display_name=app_display_name, appimage_path=appimage_path
                )

                assert success is False
                assert "file system error" in message
                mock_error.assert_called_once()

    def test_create_or_update_desktop_entry_unexpected_error(
        self, desktop_manager: DesktopEntryManager
    ) -> None:
        """Test create_or_update_desktop_entry with unexpected error.

        Args:
            desktop_manager: DesktopEntryManager instance

        """
        app_display_name = "TestApp"
        appimage_path = "/path/to/TestApp.AppImage"

        with patch.object(
            desktop_manager, "read_desktop_file", side_effect=ValueError("Test error")
        ):
            with patch("logging.Logger.error") as mock_error:
                success, message = desktop_manager.create_or_update_desktop_entry(
                    app_display_name=app_display_name, appimage_path=appimage_path
                )

                assert success is False
                assert "Unexpected error" in message
                mock_error.assert_called_once()
