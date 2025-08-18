from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.commands.remove import RemoveHandler
from my_unicorn.desktop import ConfigManager


@pytest.fixture
def mock_config_manager():
    """Fixture to mock the configuration manager."""
    config_manager = MagicMock()
    config_manager.load_global_config.return_value = {
        "directory": {
            "storage": Path("/mock/storage"),
            "icon": Path("/mock/icons"),
        }
    }
    config_manager.load_app_config.side_effect = (
        lambda app_name: {
            "appimage": {"name": f"{app_name}.AppImage", "rename": app_name},
            "icon": {"name": f"{app_name}.png", "installed": True},
        }
        if app_name != "missing_app"
        else None
    )
    config_manager.remove_app_config = MagicMock()
    return config_manager


@pytest.fixture
def mock_global_config():
    """Fixture to mock the global configuration."""
    from pathlib import Path

    return {
        "directory": {
            "storage": Path("/mock/storage"),
            "icon": Path("/mock/icons"),
        }
    }


@pytest.fixture
def remove_handler(mock_config_manager, mock_global_config):
    """Fixture to create a RemoveHandler instance with mocked dependencies."""
    return RemoveHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_remove_single_app_success(
    remove_handler, mock_config_manager, mock_global_config
):
    """Test successful removal of a single app."""
    storage_dir = mock_global_config["directory"]["storage"]
    icon_dir = mock_global_config["directory"]["icon"]

    # Mock file existence and unlink behavior
    appimage_path = storage_dir / "test_app.AppImage"
    clean_appimage_path = storage_dir / "test_app.appimage"
    icon_path = icon_dir / "test_app.png"

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.desktop.ConfigManager", return_value=ConfigManager()
        ) as MockConfigManager,
        patch("builtins.print") as mock_print,
    ):
        mock_appimage_unlink = mock_unlink
        mock_clean_appimage_unlink = mock_unlink
        mock_icon_unlink = mock_unlink
        print(f"Debugging paths: {appimage_path}, {clean_appimage_path}, {icon_path}")
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # Verify unlink calls
        expected_calls = [
            ((appimage_path,),),
            ((clean_appimage_path,),),
            ((icon_path,),),
            # Desktop entry file is also unlinked, but path is dynamic.
        ]
        # Check that the expected files were unlinked
        mock_unlink.assert_any_call(appimage_path)
        mock_unlink.assert_any_call(clean_appimage_path)
        mock_unlink.assert_any_call(icon_path)
        # There should be 4 calls: AppImage, clean AppImage, desktop entry, icon
        assert mock_unlink.call_count == 4

        # Verify config removal
        mock_config_manager.remove_app_config.assert_called_once_with("test_app")


@pytest.mark.asyncio
async def test_remove_single_app_keep_config(
    remove_handler, mock_config_manager, mock_global_config
):
    """Test removal of a single app while keeping its config."""
    storage_dir = mock_global_config["directory"]["storage"]
    icon_dir = mock_global_config["directory"]["icon"]

    # Mock file existence and unlink behavior
    appimage_path = storage_dir / "test_app.AppImage"
    clean_appimage_path = storage_dir / "test_app.appimage"
    icon_path = icon_dir / "test_app.png"

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.desktop.ConfigManager", return_value=ConfigManager()
        ) as MockConfigManager,
        patch("builtins.print") as mock_print,
    ):
        args = Namespace(apps=["test_app"], keep_config=True)
        await remove_handler.execute(args)

        # Verify unlink calls
        mock_unlink.assert_any_call(appimage_path)
        mock_unlink.assert_any_call(clean_appimage_path)
        mock_unlink.assert_any_call(icon_path)
        # There should be 4 calls: AppImage, clean AppImage, desktop entry, icon
        assert mock_unlink.call_count == 4

        # Verify config is not removed
        mock_config_manager.remove_app_config.assert_not_called()


@pytest.mark.asyncio
async def test_remove_icon_always_attempted(
    remove_handler, mock_config_manager, mock_global_config
):
    """Test that icon is always attempted to be removed if icon config is present."""
    storage_dir = mock_global_config["directory"]["storage"]
    icon_dir = mock_global_config["directory"]["icon"]

    appimage_path = storage_dir / "test_app.AppImage"
    clean_appimage_path = storage_dir / "test_app.appimage"
    icon_path = icon_dir / "test_app.png"

    # Remove 'installed' flag from icon config to simulate missing flag
    mock_config_manager.load_app_config.side_effect = (
        lambda app_name: {
            "appimage": {"name": f"{app_name}.AppImage", "rename": app_name},
            "icon": {"name": f"{app_name}.png"},  # no 'installed'
        }
        if app_name != "missing_app"
        else None
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch("my_unicorn.desktop.ConfigManager", return_value=ConfigManager()),
        patch("builtins.print") as mock_print,
    ):
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # Icon should still be attempted to be removed
        mock_unlink.assert_any_call(icon_path)


@pytest.mark.asyncio
async def test_remove_missing_app(remove_handler, mock_config_manager):
    """Test removal of a missing app."""
    args = Namespace(apps=["missing_app"], keep_config=False)

    with patch("builtins.print") as mock_print:
        await remove_handler.execute(args)

        # Verify error message
        mock_print.assert_any_call("❌ App 'missing_app' not found")

        # Verify config is not removed
        mock_config_manager.remove_app_config.assert_not_called()


@pytest.mark.asyncio
async def test_remove_app_with_desktop_entry_error(
    remove_handler, mock_config_manager, mock_global_config
):
    """Test removal of an app with a desktop entry removal error."""
    storage_dir = mock_global_config["directory"]["storage"]
    icon_dir = mock_global_config["directory"]["icon"]

    # Mock file existence and unlink behavior
    appimage_path = storage_dir / "test_app.AppImage"
    clean_appimage_path = storage_dir / "test_app.appimage"
    icon_path = icon_dir / "test_app.png"

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.desktop.remove_desktop_entry_for_app",
            side_effect=Exception("Desktop entry error"),
        ) as mock_remove_desktop_entry,
        patch(
            "my_unicorn.desktop.ConfigManager", return_value=ConfigManager()
        ) as MockConfigManager,
        patch("builtins.print") as mock_print,
    ):
        print(
            f"Debugging paths: appimage_path={appimage_path}, clean_appimage_path={clean_appimage_path}, icon_path={icon_path}"
        )
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # Verify unlink calls
        mock_unlink.assert_any_call(appimage_path)
        mock_unlink.assert_any_call(clean_appimage_path)
        mock_unlink.assert_any_call(icon_path)
        # There should be 3 calls: AppImage, clean AppImage, icon (desktop entry fails)
        assert mock_unlink.call_count == 3

        # Verify desktop entry removal error is logged
        mock_remove_desktop_entry.assert_called_once_with("test_app", mock_config_manager)
