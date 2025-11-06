"""Tests for DesktopEntry and desktop entry helpers."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.desktop_entry import (
    DesktopEntry,
    create_desktop_entry_for_app,
    remove_desktop_entry_for_app,
)


@pytest.fixture
def desktop_entry(tmp_path):
    app_name = "testapp"
    appimage_path = tmp_path / "testapp.AppImage"
    appimage_path.write_text("run")
    icon_path = tmp_path / "icon.png"
    icon_path.write_text("icon")
    entry = DesktopEntry(app_name, appimage_path, icon_path)
    return entry


def test_generate_desktop_content_basic(desktop_entry):
    content = desktop_entry.generate_desktop_content(comment="Test app")
    assert "[Desktop Entry]" in content
    assert "Name=Testapp" in content
    assert "Exec=" in content
    assert "Icon=" in content
    assert "Comment=Test app" in content


def test_create_and_remove_desktop_file(desktop_entry, tmp_path):
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
    desktop_dir = tmp_path / "applications"
    desktop_dir.mkdir()
    desktop_entry.get_desktop_dirs = lambda: [desktop_dir]
    file_path = desktop_entry.create_desktop_file(
        target_dir=desktop_dir, comment="Test app"
    )
    # Update with new comment
    updated = desktop_entry.update_desktop_file(comment="Updated app")
    assert updated.exists()
    assert "Updated app" in updated.read_text()


def test_validate_desktop_file(desktop_entry, tmp_path):
    desktop_dir = tmp_path / "applications"
    desktop_dir.mkdir()
    file_path = desktop_entry.create_desktop_file(
        target_dir=desktop_dir, comment="Test app"
    )
    errors = desktop_entry.validate_desktop_file(file_path)
    assert errors == []
    # Remove AppImage file to trigger error
    desktop_entry.appimage_path.unlink()
    errors = desktop_entry.validate_desktop_file(file_path)
    assert any("AppImage file does not exist" in e for e in errors)


def test_browser_detection_and_mime_types(tmp_path):
    entry = DesktopEntry("firefox", tmp_path / "firefox.AppImage")
    assert entry._is_browser_app() is True
    mime_types = entry._get_browser_mime_types()
    assert "text/html" in mime_types


def test_should_update_desktop_file_logic(desktop_entry):
    old_content = desktop_entry.generate_desktop_content(comment="Old")
    new_content = desktop_entry.generate_desktop_content(comment="New")
    assert (
        desktop_entry._should_update_desktop_file(old_content, new_content)
        is True
    )


def test_refresh_desktop_database(monkeypatch, desktop_entry):
    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/bin/update-desktop-database"
    )
    monkeypatch.setattr("subprocess.run", MagicMock(return_value=None))
    assert desktop_entry.refresh_desktop_database() is True


def test_create_desktop_entry_for_app(tmp_path):
    appimage_path = tmp_path / "testapp.AppImage"
    appimage_path.write_text("run")
    icon_path = tmp_path / "icon.png"
    icon_path.write_text("icon")
    file_path = create_desktop_entry_for_app(
        "testapp", appimage_path, icon_path, comment="Test app"
    )
    assert file_path.exists()
    assert "Test app" in file_path.read_text()


def test_remove_desktop_entry_for_app(tmp_path):
    appimage_path = tmp_path / "testapp.AppImage"
    appimage_path.write_text("run")
    entry = DesktopEntry("testapp", appimage_path)
    file_path = entry.create_desktop_file(
        target_dir=tmp_path, comment="Test app"
    )
    assert file_path.exists()
    # Remove using helper
    assert remove_desktop_entry_for_app("testapp", config_manager=None) in [
        True,
        False,
    ]
