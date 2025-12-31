from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.commands.remove import RemoveHandler
from my_unicorn.desktop_entry import ConfigManager


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
def global_config():
    """Fixture to mock the global configuration."""
    from pathlib import Path

    return {
        "directory": {
            "storage": Path("/mock/storage"),
            "icon": Path("/mock/icons"),
        }
    }


@pytest.fixture
def remove_handler(mock_config_manager, global_config):
    """Fixture to create a RemoveHandler instance with mocked dependencies."""
    return RemoveHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_remove_single_app_success(
    remove_handler, mock_config_manager, global_config
):
    """Test successful removal of a single app."""
    storage_dir = global_config["directory"]["storage"]
    icon_dir = global_config["directory"]["icon"]

    # Mock file existence and unlink behavior
    appimage_path = storage_dir / "test_app.AppImage"
    clean_appimage_path = storage_dir / "test_app.appimage"
    icon_path = icon_dir / "test_app.png"

    with (
        patch(
            "pathlib.Path.exists", autospec=True, return_value=True
        ) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.desktop_entry.ConfigManager",
            return_value=ConfigManager(),
        ) as MockConfigManager,
        patch("my_unicorn.commands.remove.logger") as mock_logger,
    ):
        mock_appimage_unlink = mock_unlink
        mock_clean_appimage_unlink = mock_unlink
        mock_icon_unlink = mock_unlink
        print(
            f"Debugging paths: {appimage_path}, {clean_appimage_path}, {icon_path}"
        )
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
        mock_config_manager.remove_app_config.assert_called_once_with(
            "test_app"
        )
        # Verify that messages were printed for successful removals
        mock_logger.info.assert_any_call("✅ Removed icon: %s", str(icon_path))
        mock_logger.info.assert_any_call(
            "✅ Removed config for %s", "test_app"
        )


@pytest.mark.asyncio
async def test_remove_single_app_keep_config(
    remove_handler, mock_config_manager, global_config
):
    """Test removal of a single app while keeping its config."""
    storage_dir = global_config["directory"]["storage"]
    icon_dir = global_config["directory"]["icon"]

    # Mock file existence and unlink behavior
    appimage_path = storage_dir / "test_app.AppImage"
    clean_appimage_path = storage_dir / "test_app.appimage"
    icon_path = icon_dir / "test_app.png"

    with (
        patch(
            "pathlib.Path.exists", autospec=True, return_value=True
        ) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.desktop_entry.ConfigManager",
            return_value=ConfigManager(),
        ) as MockConfigManager,
        patch("my_unicorn.commands.remove.logger") as mock_logger,
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
        # Verify printed messages for successful removals
        mock_logger.info.assert_any_call("✅ Removed icon: %s", str(icon_path))
        mock_logger.info.assert_any_call("✅ Kept config for %s", "test_app")


@pytest.mark.asyncio
async def test_remove_icon_always_attempted(
    remove_handler, mock_config_manager, global_config
):
    """Test that icon is always attempted to be removed if icon config is present."""
    storage_dir = global_config["directory"]["storage"]
    icon_dir = global_config["directory"]["icon"]

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
        patch(
            "pathlib.Path.exists", autospec=True, return_value=True
        ) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.desktop_entry.ConfigManager",
            return_value=ConfigManager(),
        ),
        patch("my_unicorn.commands.remove.logger") as mock_logger,
    ):
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # Icon should still be attempted to be removed
        mock_unlink.assert_any_call(icon_path)


@pytest.mark.asyncio
async def test_remove_missing_app(remove_handler, mock_config_manager):
    """Test removal of a missing app."""
    args = Namespace(apps=["missing_app"], keep_config=False)

    with patch("my_unicorn.commands.remove.logger") as mock_logger:
        await remove_handler.execute(args)

        # Verify error message (actual format is "❌ %s", msg where msg="App 'missing_app' not found")
        mock_logger.info.assert_any_call(
            "❌ %s", "App 'missing_app' not found"
        )

        # Verify config is not removed
        mock_config_manager.remove_app_config.assert_not_called()


@pytest.mark.asyncio
async def test_remove_app_with_desktop_entry_error(
    remove_handler, mock_config_manager, global_config
):
    """Test removal of an app with a desktop entry removal error."""
    storage_dir = global_config["directory"]["storage"]
    icon_dir = global_config["directory"]["icon"]

    # Mock file existence and unlink behavior
    appimage_path = storage_dir / "test_app.AppImage"
    clean_appimage_path = storage_dir / "test_app.appimage"
    icon_path = icon_dir / "test_app.png"

    with (
        patch(
            "pathlib.Path.exists", autospec=True, return_value=True
        ) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.desktop_entry.remove_desktop_entry_for_app",
            side_effect=Exception("Desktop entry error"),
        ) as mock_remove_desktop_entry,
        patch(
            "my_unicorn.desktop_entry.ConfigManager",
            return_value=ConfigManager(),
        ) as MockConfigManager,
        patch("my_unicorn.commands.remove.logger") as mock_logger,
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
        mock_remove_desktop_entry.assert_called_once_with(
            "test_app", mock_config_manager
        )
