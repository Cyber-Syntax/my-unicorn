"""Tests for DesktopEntry and desktop entry helpers."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.constants import DESKTOP_BROWSER_MIME_TYPES
from my_unicorn.core.desktop_entry import (
    DesktopEntry,
    is_browser_app,
    should_update_desktop_file,
    validate_desktop_file,
)


@pytest.fixture
def desktop_entry(tmp_path):
    """Create a DesktopEntry instance backed by temp AppImage/icon files."""
    app_name = "testapp"
    appimage_path = tmp_path / "testapp.AppImage"
    appimage_path.write_text("run")
    icon_path = tmp_path / "icon.png"
    icon_path.write_text("icon")
    return DesktopEntry(app_name, appimage_path, icon_path)


def test_generate_desktop_content_basic(desktop_entry):
    """Generates basic desktop entry content with required fields."""
    content = desktop_entry.generate_desktop_content(comment="Test app")
    assert "[Desktop Entry]" in content
    assert "Name=Testapp" in content
    assert "Exec=" in content
    assert "Icon=" in content
    assert "Comment=Test app" in content


def test_create_and_remove_desktop_file(desktop_entry, tmp_path):
    """Creates and removes the .desktop file as expected."""
    desktop_dir = tmp_path / "applications"
    desktop_dir.mkdir()
    desktop_entry.get_desktop_dirs = lambda: [desktop_dir]
    file_path = desktop_entry.create_desktop_file(
        target_dir=desktop_dir, comment="Test app"
    )
    assert file_path.exists()
    assert desktop_entry.is_installed()
    assert "Test app" in file_path.read_text()
    assert desktop_entry.remove_desktop_file() is True
    assert not file_path.exists()
    # Remove again should return False
    assert desktop_entry.remove_desktop_file() is False


def test_update_desktop_file(desktop_entry, tmp_path):
    """Updates an existing desktop file's content."""
    desktop_dir = tmp_path / "applications"
    desktop_dir.mkdir()
    desktop_entry.get_desktop_dirs = lambda: [desktop_dir]
    desktop_entry.create_desktop_file(
        target_dir=desktop_dir, comment="Test app"
    )
    # Update with new comment
    updated = desktop_entry.update_desktop_file(comment="Updated app")
    assert updated.exists()
    assert "Updated app" in updated.read_text()


def test_validate_desktop_file(desktop_entry, tmp_path):
    """Validates desktop file and reports missing AppImage paths."""
    desktop_dir = tmp_path / "applications"
    desktop_dir.mkdir()
    file_path = desktop_entry.create_desktop_file(
        target_dir=desktop_dir, comment="Test app"
    )
    errors = validate_desktop_file(file_path)
    assert errors == []
    # Remove AppImage file to trigger error
    desktop_entry.appimage_path.unlink()
    errors = validate_desktop_file(file_path)
    assert any("AppImage file does not exist" in e for e in errors)


def test_browser_detection_and_mime_types(tmp_path):
    """Detects browsers and provides standard browser MIME types."""
    entry = DesktopEntry("firefox", tmp_path / "firefox.AppImage")
    assert is_browser_app(entry.app_name) is True
    assert "text/html" in DESKTOP_BROWSER_MIME_TYPES


def test_should_update_desktop_file_logic(desktop_entry):
    """Detects when desktop content should be updated."""
    old_content = desktop_entry.generate_desktop_content(comment="Old")
    new_content = desktop_entry.generate_desktop_content(comment="New")
    assert should_update_desktop_file(old_content, new_content) is True


def test_refresh_desktop_database(monkeypatch, desktop_entry):
    """Refreshes the desktop database when the binary is available."""
    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/bin/update-desktop-database"
    )
    monkeypatch.setattr("subprocess.run", MagicMock(return_value=None))
    assert desktop_entry.refresh_desktop_database() is True


def test_remove_desktop_entry_for_app(tmp_path):
    """Removes a desktop entry via the instance method."""
    appimage_path = tmp_path / "testapp.AppImage"
    appimage_path.write_text("run")
    entry = DesktopEntry("testapp", appimage_path)
    desktop_dir = tmp_path / "applications"
    desktop_dir.mkdir()
    entry.get_desktop_dirs = lambda: [desktop_dir]
    file_path = entry.create_desktop_file(
        target_dir=desktop_dir, comment="Test app"
    )
    assert file_path.exists()
    # Remove using instance method and verify it succeeded
    assert entry.remove_desktop_file() is True
    assert not file_path.exists()
    # Verify removing again returns False (file already gone)
    assert entry.remove_desktop_file() is False
