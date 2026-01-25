from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.cli.commands.remove import RemoveHandler
from my_unicorn.core.desktop_entry import ConfigManager


@pytest.fixture
def mock_config_manager():
    """Fixture to mock the configuration manager with v2 config format."""
    config_manager = MagicMock()
    config_manager.load_global_config.return_value = {
        "directory": {
            "storage": Path("/mock/storage"),
            "icon": Path("/mock/icons"),
        }
    }

    def load_app_config_side_effect(app_name):
        if app_name == "missing_app":
            return None
        # v2 format
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": app_name,
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": f"/mock/storage/{app_name}.AppImage",
                "verification": {"passed": True, "methods": []},
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": f"/mock/icons/{app_name}.png",
                },
            },
        }

    def get_effective_config_side_effect(app_name):
        if app_name == "missing_app":
            raise ValueError(f"No config found for {app_name}")
        return {
            "config_version": "2.0.0",
            "metadata": {"name": app_name, "display_name": app_name.title()},
            "source": {
                "type": "github",
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": f"/mock/storage/{app_name}.AppImage",
                "verification": {"passed": True, "methods": []},
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": f"/mock/icons/{app_name}.png",
                },
            },
        }

    config_manager.load_app_config.side_effect = load_app_config_side_effect
    config_manager.app_config_manager.get_effective_config.side_effect = (
        get_effective_config_side_effect
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
    icon_path = Path("/mock/icons/test_app.png")
    appimage_path = Path("/mock/storage/test_app.AppImage")

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    with (
        patch(
            "pathlib.Path.exists", autospec=True, return_value=True
        ) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.core.cache.get_cache_manager",
            return_value=mock_cache_manager,
        ),
    ):
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # Verify files were unlinked (appimage, desktop, icon)
        assert mock_unlink.call_count == 3

        # Verify config removal
        mock_config_manager.remove_app_config.assert_called_once_with(
            "test_app"
        )


@pytest.mark.asyncio
async def test_remove_single_app_keep_config(
    remove_handler, mock_config_manager, global_config
):
    """Test removal of a single app while keeping its config."""
    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    with (
        patch(
            "pathlib.Path.exists", autospec=True, return_value=True
        ) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.core.cache.get_cache_manager",
            return_value=mock_cache_manager,
        ),
    ):
        args = Namespace(apps=["test_app"], keep_config=True)
        await remove_handler.execute(args)

        # Verify files were unlinked (appimage, desktop, icon)
        assert mock_unlink.call_count == 3

        # Verify config is not removed
        mock_config_manager.remove_app_config.assert_not_called()


@pytest.mark.asyncio
async def test_remove_icon_always_attempted(
    remove_handler, mock_config_manager, global_config
):
    """Test that icon is always attempted to be removed if icon config is present."""
    storage_dir = global_config["directory"]["storage"]
    icon_dir = global_config["directory"]["icon"]

    icon_path = icon_dir / "test_app.png"

    # Override with v2 config that has icon in state
    mock_config_manager.load_app_config.side_effect = (
        lambda app_name: {
            "state": {
                "icon": {"path": f"/mock/icons/{app_name}.png"},
            },
            "effective_config": {
                "source": {"owner": "test-owner", "repo": "test-repo"},
            },
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
            "my_unicorn.config.ConfigManager",
            return_value=ConfigManager(),
        ),
        patch(
            "my_unicorn.core.cache.get_cache_manager",
            return_value=AsyncMock(),
        ) as mock_get_cache,
    ):
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # Icon should still be attempted to be removed
        mock_unlink.assert_any_call(icon_path)


@pytest.mark.asyncio
async def test_remove_missing_app(remove_handler, mock_config_manager, caplog):
    """Test removal of a missing app logs error without raising."""
    args = Namespace(apps=["missing_app"], keep_config=False)

    await remove_handler.execute(args)

    # Should log error message instead of raising
    assert "App 'missing_app' not found" in caplog.text
    assert "ERROR" in caplog.text


@pytest.mark.asyncio
async def test_remove_app_with_desktop_entry_error(
    remove_handler, mock_config_manager, global_config
):
    """Test removal of an app with a desktop entry removal error."""
    storage_dir = global_config["directory"]["storage"]
    icon_dir = global_config["directory"]["icon"]

    # Mock file existence and unlink behavior - using single path for v2
    appimage_path = storage_dir / "test_app.AppImage"
    icon_path = icon_dir / "test_app.png"

    with (
        patch(
            "pathlib.Path.exists", autospec=True, return_value=True
        ) as mock_exists,
        patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
        patch(
            "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
            side_effect=Exception("Desktop entry error"),
        ) as mock_remove_desktop_entry,
        patch(
            "my_unicorn.config.ConfigManager",
            return_value=ConfigManager(),
        ) as MockConfigManager,
        patch(
            "my_unicorn.core.cache.get_cache_manager",
            return_value=AsyncMock(),
        ) as mock_get_cache,
    ):
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # V2 removes only AppImage and icon (2 files total) when desktop entry fails
        # Note: clean_appimage_path is removed in v1, but v2 only has state.installed_path
        assert mock_unlink.call_count == 2
        mock_unlink.assert_any_call(appimage_path)
        mock_unlink.assert_any_call(icon_path)

        # Verify desktop entry removal error is logged
        mock_remove_desktop_entry.assert_called_once_with(
            "test_app", mock_config_manager
        )
