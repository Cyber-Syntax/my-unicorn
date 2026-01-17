"""Unit tests for the RemoveService receiver."""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.workflows.remove import RemoveService
from my_unicorn.types import AppConfig, GlobalConfig


@pytest.fixture
def mock_config_manager():
    """Return a mock configuration manager for testing."""
    config_manager = MagicMock()
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
    """Return a mock global config mapping with directories."""
    return {
        "directory": {
            "storage": Path("/mock/storage"),
            "icon": Path("/mock/icons"),
            "backup": Path("/mock/backups"),
        }
    }


@pytest.mark.asyncio
async def test_remove_app_success(mock_config_manager, global_config):
    """Removal should succeed and report expected flags when app exists."""
    service = RemoveService(mock_config_manager, global_config)

    # Paths obtained for readability, not used directly

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
        patch(
            "my_unicorn.core.cache.get_cache_manager",
        ) as mock_get_cache,
        patch(
            "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
        ),
    ):
        mock_cache_manager = MagicMock()
        mock_get_cache.return_value = mock_cache_manager

        result = await service.remove_app("test_app", keep_config=False)

        assert result["success"] is True
        assert result["config_removed"] is True
        assert result["icon_removed"] is True
        assert isinstance(result["backup_removed"], bool)
        MIN_UNLINKS = 3
        assert unlink_mock.call_count >= MIN_UNLINKS


@pytest.mark.asyncio
async def test_remove_app_icon_removed_when_present(
    mock_config_manager, global_config
):
    """Icon file should be removed (unlink called) when the icon exists in icon dir."""
    service = RemoveService(mock_config_manager, global_config)

    icon_dir = global_config["directory"]["icon"]
    expected_icon_path = icon_dir / "test_app.png"

    def exists_side_effect(self_path):
        # For this test, all relevant paths exist
        return True

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=exists_side_effect,
        ),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=True)

        assert result["success"] is True
        assert result["icon_removed"] is True
        # Check that unlink was called for the expected icon path
        assert any(
            str(expected_icon_path) in str(call.args[0])
            for call in unlink_mock.call_args_list
        )


@pytest.mark.asyncio
async def test_remove_app_icon_skipped_when_missing(
    mock_config_manager, global_config
):
    """Icon removal should be skipped when the icon does not exist."""
    service = RemoveService(mock_config_manager, global_config)

    icon_dir = global_config["directory"]["icon"]
    expected_icon_path = icon_dir / "test_app.png"

    def exists_side_effect(self_path):
        # icon path is missing, others exist
        return str(self_path) != str(expected_icon_path)

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=exists_side_effect,
        ),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=True)

        assert result["success"] is True
        assert result["icon_removed"] is False
        # Ensure unlink was not called with expected icon path
        assert not any(
            str(expected_icon_path) in str(call.args[0])
            for call in unlink_mock.call_args_list
        )


@pytest.mark.asyncio
async def test_remove_app_cache_and_backup_clear(global_config):
    """Cache should be cleared and backups removed when owner/repo is present."""
    # Build a custom config manager with owner/repo and appimage/icon info
    custom_config_manager = MagicMock()
    custom_config_manager.load_app_config.return_value = {
        "owner": "test_owner",
        "repo": "test_repo",
        "appimage": {"name": "test_app.AppImage", "rename": "test_app"},
        "icon": {"name": "test_app.png", "installed": True},
    }
    custom_config_manager.remove_app_config = MagicMock()

    service = RemoveService(custom_config_manager, global_config)

    # backup_dir value is used indirectly by mocked Path.exists

    def exists_side_effect(self_path):
        # Simulate that all paths exist including backup dir
        return True

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=exists_side_effect,
        ),
        patch("pathlib.Path.unlink", autospec=True),
        patch(
            "my_unicorn.core.cache.get_cache_manager",
            return_value=mock_cache_manager,
        ),
        patch("shutil.rmtree") as rmtree_mock,
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        # Cache should be cleared
        assert result["cache_cleared"] is True
        mock_cache_manager.clear_cache.assert_awaited_once_with(
            "test_owner", "test_repo"
        )

        # Backup should have been removed
        assert result["backup_removed"] is True
        rmtree_mock.assert_called_once()


@pytest.mark.asyncio
async def test_remove_missing_app(mock_config_manager, global_config):
    """Removing a non-existent app should return success=False and an error."""
    service = RemoveService(mock_config_manager, global_config)

    result = await service.remove_app("missing_app", keep_config=False)

    assert result["success"] is False
    assert "not found" in result.get("error", "")


@pytest.mark.asyncio
async def test_remove_appimage_files_removes_files(
    mock_config_manager,
    global_config,
):
    """_remove_appimage_files removes the named and normalized AppImage files."""
    service = RemoveService(mock_config_manager, global_config)

    storage_dir = global_config["directory"]["storage"]
    app_config = cast(
        "AppConfig",
        {
            "appimage": {
                "name": "test_app.AppImage",
                "rename": "test_app",
            }
        },
    )

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            return_value=True,
        ),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
    ):
        removed = service._remove_appimage_files(app_config, storage_dir)

        # Both paths should be removed
        MIN_REMOVED = 2
        assert len(removed) == MIN_REMOVED
        assert unlink_mock.call_count >= MIN_REMOVED


@pytest.mark.asyncio
async def test_clear_cache_calls_api_when_owner_repo_present(global_config):
    """_clear_cache should call the cache manager when owner and repo exist."""
    mock_config_manager = MagicMock()
    service = RemoveService(mock_config_manager, global_config)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    with patch(
        "my_unicorn.core.cache.get_cache_manager",
        return_value=mock_cache_manager,
    ):
        app_config = cast(
            "AppConfig", {"owner": "o", "repo": "r", "appimage": {"name": "x"}}
        )
        cleared = await service._clear_cache(app_config)
        assert cleared is True
        mock_cache_manager.clear_cache.assert_awaited_once_with("o", "r")


@pytest.mark.asyncio
async def test_clear_cache_skips_when_owner_repo_missing(global_config):
    """_clear_cache should skip when owner or repo are missing."""
    service = RemoveService(MagicMock(), global_config)
    app_config = cast(
        "AppConfig", {"owner": None, "repo": None, "appimage": {"name": "x"}}
    )
    cleared = await service._clear_cache(app_config)
    assert cleared is False


def test_remove_backups_removes_and_returns_path(global_config):
    """_remove_backups should call shutil.rmtree when backup dir exists."""
    mock_config_manager = MagicMock()
    service = RemoveService(mock_config_manager, global_config)

    def exists_side_effect(path_obj):
        return True

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=exists_side_effect,
        ),
        patch("shutil.rmtree") as rmtree_mock,
    ):
        removed, path = service._remove_backups("test_app")
        assert removed is True
        assert isinstance(path, str)
        rmtree_mock.assert_called_once()


def test_remove_backups_skips_when_not_configured(global_config):
    """_remove_backups returns (False, None) when backup not configured."""
    mock_config_manager = MagicMock()
    config = cast(
        "GlobalConfig",
        {
            "directory": {
                "storage": Path("/mock/storage"),
                "icon": Path("/mock/icons"),
                "backup": None,
                "repo": Path("/x"),
                "package": Path("/x"),
                "download": Path("/x"),
                "settings": Path("/x"),
                "logs": Path("/x"),
                "cache": Path("/x"),
                "tmp": Path("/x"),
            }
        },
    )
    service = RemoveService(mock_config_manager, config)
    removed, path = service._remove_backups("test_app")
    assert removed is False
    assert path is None


def test_remove_desktop_entry(mock_config_manager, global_config):
    """_remove_desktop_entry returns True/False."""
    service = RemoveService(mock_config_manager, global_config)

    with patch(
        "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
        return_value=True,
    ):
        assert service._remove_desktop_entry("test_app") is True

    with patch(
        "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
        return_value=False,
    ):
        assert service._remove_desktop_entry("test_app") is False


def test_remove_icon_remove_and_report(mock_config_manager, global_config):
    """_remove_icon removes icon when present and returns its path."""
    service = RemoveService(mock_config_manager, global_config)
    app_config = cast(
        "AppConfig",
        {
            "icon": {"name": "test_app.png", "installed": True},
            "appimage": {"name": "x"},
        },
    )

    def exists_side_effect(path_obj):
        return True

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=exists_side_effect,
        ),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
    ):
        removed, path = service._remove_icon(app_config)
        assert removed is True
        assert isinstance(path, str)
        assert unlink_mock.called


def test_remove_icon_skipped_when_missing(mock_config_manager, global_config):
    """_remove_icon should no-op when the icon is missing."""
    service = RemoveService(mock_config_manager, global_config)
    app_config = cast(
        "AppConfig",
        {
            "icon": {"name": "test_app.png", "installed": True},
            "appimage": {"name": "x"},
        },
    )

    def exists_side_effect(path_obj):
        return False

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=exists_side_effect,
        ),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
    ):
        removed, path = service._remove_icon(app_config)
        assert removed is False
        assert isinstance(path, str)
        assert not unlink_mock.called


def test_remove_config_calls_manager(mock_config_manager, global_config):
    """_remove_config returns truthiness after calling remove_app_config."""
    service = RemoveService(mock_config_manager, global_config)
    mock_config_manager.remove_app_config.return_value = True
    assert service._remove_config("test_app") is True

    mock_config_manager.remove_app_config.return_value = False
    assert service._remove_config("test_app") is False
