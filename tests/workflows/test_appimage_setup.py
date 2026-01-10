"""Tests for appimage_setup utility module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRenameAppimage:
    """Tests for rename_appimage function."""

    def test_rename_appimage_from_catalog(self):
        """Test rename_appimage using catalog entry."""
        from my_unicorn.workflows.appimage_setup import rename_appimage

        appimage_path = Path("/tmp/test.AppImage")
        catalog_entry = {"appimage": {"rename": "MyApp"}}
        storage_service = MagicMock()
        storage_service.get_clean_appimage_name.return_value = "MyApp"
        storage_service.rename_appimage.return_value = Path(
            "/tmp/MyApp.AppImage"
        )

        result = rename_appimage(
            appimage_path=appimage_path,
            app_name="testapp",
            app_config={},
            catalog_entry=catalog_entry,
            storage_service=storage_service,
        )

        storage_service.get_clean_appimage_name.assert_called_once_with(
            "MyApp"
        )
        storage_service.rename_appimage.assert_called_once()
        assert result == Path("/tmp/MyApp.AppImage")

    def test_rename_appimage_from_app_config(self):
        """Test rename_appimage using app config."""
        from my_unicorn.workflows.appimage_setup import rename_appimage

        appimage_path = Path("/tmp/test.AppImage")
        app_config = {"appimage": {"rename": "ConfigApp"}}
        storage_service = MagicMock()
        storage_service.get_clean_appimage_name.return_value = "ConfigApp"
        storage_service.rename_appimage.return_value = Path(
            "/tmp/ConfigApp.AppImage"
        )

        result = rename_appimage(
            appimage_path=appimage_path,
            app_name="testapp",
            app_config=app_config,
            catalog_entry=None,
            storage_service=storage_service,
        )

        storage_service.get_clean_appimage_name.assert_called_once_with(
            "ConfigApp"
        )
        assert result == Path("/tmp/ConfigApp.AppImage")

    def test_rename_appimage_fallback_to_app_name(self):
        """Test rename_appimage fallback to app_name when no rename config."""
        from my_unicorn.workflows.appimage_setup import rename_appimage

        appimage_path = Path("/tmp/test.AppImage")
        storage_service = MagicMock()
        storage_service.get_clean_appimage_name.return_value = "testapp"
        storage_service.rename_appimage.return_value = Path(
            "/tmp/testapp.AppImage"
        )

        result = rename_appimage(
            appimage_path=appimage_path,
            app_name="testapp",
            app_config={},
            catalog_entry=None,
            storage_service=storage_service,
        )

        storage_service.get_clean_appimage_name.assert_called_once_with(
            "testapp"
        )
        assert result == Path("/tmp/testapp.AppImage")

    def test_rename_appimage_catalog_priority(self):
        """Test that catalog entry takes priority over app config."""
        from my_unicorn.workflows.appimage_setup import rename_appimage

        appimage_path = Path("/tmp/test.AppImage")
        catalog_entry = {"appimage": {"rename": "CatalogName"}}
        app_config = {"appimage": {"rename": "ConfigName"}}
        storage_service = MagicMock()
        storage_service.get_clean_appimage_name.return_value = "CatalogName"
        storage_service.rename_appimage.return_value = Path(
            "/tmp/CatalogName.AppImage"
        )

        result = rename_appimage(
            appimage_path=appimage_path,
            app_name="testapp",
            app_config=app_config,
            catalog_entry=catalog_entry,
            storage_service=storage_service,
        )

        # Should use catalog entry, not app config
        storage_service.get_clean_appimage_name.assert_called_once_with(
            "CatalogName"
        )


@pytest.mark.asyncio
class TestSetupAppimageIcon:
    """Tests for setup_appimage_icon function."""

    @patch("my_unicorn.workflows.appimage_setup.extract_icon_from_appimage")
    async def test_setup_appimage_icon_success(self, mock_extract):
        """Test setup_appimage_icon with successful extraction."""
        from my_unicorn.workflows.appimage_setup import setup_appimage_icon

        mock_extract.return_value = "/path/to/icon.png"
        appimage_path = Path("/tmp/test.AppImage")
        icon_dir = Path("/tmp/icons")

        result = await setup_appimage_icon(
            appimage_path=appimage_path,
            app_name="testapp",
            icon_dir=icon_dir,
            app_config={},
            catalog_entry=None,
        )

        assert result["success"] is True
        assert result["source"] == "extraction"
        assert result["icon_path"] == "/path/to/icon.png"
        assert result["installed"] is True
        mock_extract.assert_called_once()

    @patch("my_unicorn.workflows.appimage_setup.extract_icon_from_appimage")
    async def test_setup_appimage_icon_disabled(self, mock_extract):
        """Test setup_appimage_icon when extraction is disabled."""
        from my_unicorn.workflows.appimage_setup import setup_appimage_icon

        appimage_path = Path("/tmp/test.AppImage")
        icon_dir = Path("/tmp/icons")
        catalog_entry = {
            "icon": {"extraction": False, "filename": "custom.png"}
        }

        result = await setup_appimage_icon(
            appimage_path=appimage_path,
            app_name="testapp",
            icon_dir=icon_dir,
            app_config={},
            catalog_entry=catalog_entry,
        )

        assert result["success"] is False
        assert result["source"] == "none"
        assert result["extraction"] is False
        assert result["name"] == "custom.png"
        mock_extract.assert_not_called()

    @patch("my_unicorn.workflows.appimage_setup.extract_icon_from_appimage")
    async def test_setup_appimage_icon_extraction_error(self, mock_extract):
        """Test setup_appimage_icon when extraction fails."""
        from my_unicorn.workflows.appimage_setup import setup_appimage_icon

        mock_extract.side_effect = OSError("Extraction failed")
        appimage_path = Path("/tmp/test.AppImage")
        icon_dir = Path("/tmp/icons")

        result = await setup_appimage_icon(
            appimage_path=appimage_path,
            app_name="testapp",
            icon_dir=icon_dir,
            app_config={},
            catalog_entry=None,
        )

        assert result["success"] is False
        assert "error" in result
        assert result["error"] == "Extraction error"

    @patch("my_unicorn.workflows.appimage_setup.extract_icon_from_appimage")
    async def test_setup_appimage_icon_custom_filename(self, mock_extract):
        """Test setup_appimage_icon with custom filename."""
        from my_unicorn.workflows.appimage_setup import setup_appimage_icon

        mock_extract.return_value = "/path/to/custom.png"
        appimage_path = Path("/tmp/test.AppImage")
        icon_dir = Path("/tmp/icons")
        app_config = {"icon": {"filename": "custom_icon.png"}}

        result = await setup_appimage_icon(
            appimage_path=appimage_path,
            app_name="testapp",
            icon_dir=icon_dir,
            app_config=app_config,
            catalog_entry=None,
        )

        assert result["success"] is True
        assert result["name"] == "custom_icon.png"


class TestCreateDesktopEntry:
    """Tests for create_desktop_entry function."""

    @patch("my_unicorn.workflows.appimage_setup.DesktopEntry")
    def test_create_desktop_entry_success(self, mock_desktop_entry_class):
        """Test create_desktop_entry with successful creation."""
        from my_unicorn.workflows.appimage_setup import create_desktop_entry

        mock_desktop = MagicMock()
        mock_desktop.create_desktop_file = MagicMock(
            return_value=Path("/tmp/testapp.desktop")
        )
        mock_desktop_entry_class.return_value = mock_desktop

        appimage_path = Path("/tmp/test.AppImage")
        icon_result = {"success": True, "icon_path": "/path/to/icon.png"}
        config_manager = MagicMock()

        result = create_desktop_entry(
            appimage_path=appimage_path,
            app_name="testapp",
            icon_result=icon_result,
            config_manager=config_manager,
        )

        assert result["success"] is True
        assert result["desktop_path"] == "/tmp/testapp.desktop"
        mock_desktop.create_desktop_file.assert_called_once()

    @patch("my_unicorn.workflows.appimage_setup.DesktopEntry")
    def test_create_desktop_entry_no_icon(self, mock_desktop_entry_class):
        """Test create_desktop_entry without icon."""
        from my_unicorn.workflows.appimage_setup import create_desktop_entry

        mock_desktop = MagicMock()
        mock_desktop.create_desktop_file = MagicMock(
            return_value=Path("/tmp/testapp.desktop")
        )
        mock_desktop_entry_class.return_value = mock_desktop

        appimage_path = Path("/tmp/test.AppImage")
        icon_result = {"success": False}
        config_manager = MagicMock()

        result = create_desktop_entry(
            appimage_path=appimage_path,
            app_name="testapp",
            icon_result=icon_result,
            config_manager=config_manager,
        )

        assert result["success"] is True
        # Should still create desktop entry even without icon
        mock_desktop.create_desktop_file.assert_called_once()

    @patch("my_unicorn.workflows.appimage_setup.DesktopEntry")
    def test_create_desktop_entry_error(self, mock_desktop_entry_class):
        """Test create_desktop_entry with error."""
        from my_unicorn.workflows.appimage_setup import create_desktop_entry

        mock_desktop = MagicMock()
        mock_desktop.create_desktop_file = MagicMock(
            side_effect=Exception("Desktop entry error")
        )
        mock_desktop_entry_class.return_value = mock_desktop

        appimage_path = Path("/tmp/test.AppImage")
        icon_result = {"success": True, "icon_path": "/path/to/icon.png"}
        config_manager = MagicMock()

        result = create_desktop_entry(
            appimage_path=appimage_path,
            app_name="testapp",
            icon_result=icon_result,
            config_manager=config_manager,
        )

        assert result["success"] is False
        assert "error" in result
