"""Unit tests for the RemoveService receiver."""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.remove import RemoveService
from my_unicorn.types import GlobalConfig


@pytest.fixture
def mock_config_manager():
    """Return a mock configuration manager for testing with v2 config format."""
    config_manager = MagicMock()

    def load_app_config_side_effect(app_name):
        if app_name == "missing_app":
            return None
        # Return merged effective config (load_app_config now returns merged)
        return {
            "config_version": "2.0.0",
            "metadata": {
                "name": app_name,
                "display_name": app_name.title(),
            },
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
                "verification": {
                    "passed": True,
                    "methods": [],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": f"/mock/icons/{app_name}.png",
                },
            },
        }

    config_manager.load_app_config.side_effect = load_app_config_side_effect
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
    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()
    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    # Paths obtained for readability, not used directly

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
        patch(
            "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
        ),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        assert result.success is True
        assert result.config_removed is True
        assert result.icon_removed is True
        assert isinstance(result.backup_removed, bool)
        # Should have called unlink for appimage and icon
        MIN_UNLINKS = 2
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

        assert result.success is True
        assert result.icon_removed is True
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

        assert result.success is True
        assert result.icon_removed is False
        # Ensure unlink was not called with expected icon path
        assert not any(
            str(expected_icon_path) in str(call.args[0])
            for call in unlink_mock.call_args_list
        )


@pytest.mark.asyncio
async def test_remove_app_cache_and_backup_clear(global_config):
    """Cache should be cleared and backups removed when owner/repo is present."""
    # Build a custom config manager with v2 format config
    custom_config_manager = MagicMock()
    # load_app_config now returns merged effective config
    custom_config_manager.load_app_config.return_value = {
        "config_version": "2.0.0",
        "metadata": {"name": "test_app", "display_name": "Test App"},
        "source": {
            "type": "github",
            "owner": "test_owner",
            "repo": "test_repo",
            "prerelease": False,
        },
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {"passed": True, "methods": []},
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/mock/icons/test_app.png",
            },
        },
    }
    custom_config_manager.remove_app_config = MagicMock()

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        custom_config_manager, global_config, cache_manager=mock_cache_manager
    )

    # backup_dir value is used indirectly by mocked Path.exists

    def exists_side_effect(self_path):
        # Simulate that all paths exist including backup dir
        return True

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=exists_side_effect,
        ),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree") as rmtree_mock,
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        # Cache should be cleared
        assert result.cache_cleared is True
        mock_cache_manager.clear_cache.assert_awaited_once_with(
            "test_owner", "test_repo"
        )

        # Backup should have been removed
        assert result.backup_removed is True
        rmtree_mock.assert_called_once()


@pytest.mark.asyncio
async def test_remove_missing_app(mock_config_manager, global_config):
    """Removing a non-existent app should return success=False and an error."""
    service = RemoveService(mock_config_manager, global_config)

    result = await service.remove_app("missing_app", keep_config=False)

    assert result.success is False
    assert "not found" in (result.error or "")


@pytest.mark.asyncio
async def test_remove_appimage_files_removes_files(
    mock_config_manager,
    global_config,
):
    """_remove_appimage_files removes AppImage file from state.installed_path."""
    service = RemoveService(mock_config_manager, global_config)

    # v2 config format with installed_path in state
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "installed_path": "/mock/storage/test_app.AppImage",
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00",
            "verification": {"passed": True, "methods": []},
            "icon": {"installed": False, "method": "none", "path": ""},
        },
    }

    with (
        patch(
            "pathlib.Path.exists",
            autospec=True,
            return_value=True,
        ),
        patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
    ):
        result = service._remove_appimage_files(app_config)

        # One AppImage file should be removed
        assert result.success is True
        assert len(result.files) == 1
        assert unlink_mock.call_count == 1


@pytest.mark.asyncio
async def test_clear_cache_calls_api_when_owner_repo_present(global_config):
    """_clear_cache should call the cache manager when owner and repo exist in effective config."""
    mock_config_manager = MagicMock()
    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    # v2: owner/repo are in effective_config.source dict
    effective_config = {
        "source": {"type": "github", "owner": "o", "repo": "r"},
    }
    result = await service._clear_cache(effective_config)
    assert result.success is True
    assert result.metadata.get("owner") == "o"
    assert result.metadata.get("repo") == "r"
    mock_cache_manager.clear_cache.assert_awaited_once_with("o", "r")


@pytest.mark.asyncio
async def test_clear_cache_skips_when_owner_repo_missing(global_config):
    """_clear_cache should skip when owner or repo are missing from effective config."""
    service = RemoveService(MagicMock(), global_config)
    # Empty or missing source dict
    effective_config = {"source": {}}
    result = await service._clear_cache(effective_config)
    assert result.success is True
    assert result.metadata.get("owner") is None
    assert result.metadata.get("repo") is None


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
        result = service._remove_backups("test_app")
        assert result.success is True
        assert len(result.files) == 1
        assert isinstance(result.metadata.get("path"), str)
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
    result = service._remove_backups("test_app")
    assert result.success is True
    assert len(result.files) == 0
    assert result.metadata.get("path") is None


def test_remove_desktop_entry(mock_config_manager, global_config):
    """_remove_desktop_entry returns RemovalOperation."""
    service = RemoveService(mock_config_manager, global_config)

    with patch(
        "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
        return_value=True,
    ):
        result = service._remove_desktop_entry("test_app")
        assert result.success is True

    with patch(
        "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
        return_value=False,
    ):
        result2 = service._remove_desktop_entry("test_app")
        assert result2.success is False


def test_remove_icon_remove_and_report(mock_config_manager, global_config):
    """_remove_icon removes icon when present in state and returns its path."""
    service = RemoveService(mock_config_manager, global_config)
    # v2 config: icon path is in state.icon.path
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {"passed": True, "methods": []},
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/mock/icons/test_app.png",
            },
        },
    }

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
        result = service._remove_icon(app_config)
        assert result.success is True
        assert len(result.files) == 1
        assert result.metadata.get("path") == "/mock/icons/test_app.png"
        assert unlink_mock.called


def test_remove_icon_skipped_when_missing(mock_config_manager, global_config):
    """_remove_icon should return False when icon file doesn't exist."""
    service = RemoveService(mock_config_manager, global_config)
    # v2 config: icon path in state
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {"passed": True, "methods": []},
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/mock/icons/test_app.png",
            },
        },
    }

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
        result = service._remove_icon(app_config)
        assert result.success is True
        assert len(result.files) == 0
        assert result.metadata.get("path") == "/mock/icons/test_app.png"
        assert not unlink_mock.called


def test_remove_config_calls_manager(mock_config_manager, global_config):
    """_remove_config returns RemovalOperation after calling remove_app_config."""
    service = RemoveService(mock_config_manager, global_config)
    mock_config_manager.remove_app_config.return_value = True
    result = service._remove_config("test_app")
    assert result.success is True

    mock_config_manager.remove_app_config.return_value = False
    result2 = service._remove_config("test_app")
    assert result2.success is False
