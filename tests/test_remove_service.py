"""Unit tests for the RemoveService receiver."""

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.config.schemas import validate_app_state
from my_unicorn.core.remove import RemoveService

if TYPE_CHECKING:
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


# ============================================================================
# Task 5.1: Tests for remove command with new verification fields
# ============================================================================


@pytest.fixture
def config_with_new_verification_fields():
    """App config with new verification fields.

    Includes overall_passed, actual_method, warning, and digest fields.
    """
    return {
        "config_version": "2.0.0",
        "catalog_ref": "test_app",
        "metadata": {"name": "test_app", "display_name": "Test App"},
        "source": {
            "type": "github",
            "owner": "test-owner",
            "repo": "test-repo",
            "prerelease": False,
        },
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "digest",
                "warning": None,
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "abc123def456",
                        "computed": "abc123def456",
                        "source": "github_api",
                        "digest": "sha256:abc123def456",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/mock/icons/test_app.png",
            },
        },
    }


@pytest.mark.asyncio
async def test_remove_app_with_new_verification_fields_succeeds(
    global_config, config_with_new_verification_fields
):
    """Remove should succeed when app has new verification fields.

    Task 5.1: Verify remove command loads app state with new verification
    fields (overall_passed, actual_method, digest) without errors.
    """
    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = (
        config_with_new_verification_fields
    )
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        assert result.success is True
        assert result.app_name == "test_app"
        assert result.error is None


@pytest.mark.asyncio
async def test_remove_does_not_modify_verification_section(
    global_config, config_with_new_verification_fields
):
    """Remove should not modify the verification section of app state.

    Task 5.1: The remove command must not alter verification data.
    Verifies that verification object is unchanged during removal.
    """
    original_verification = config_with_new_verification_fields["state"][
        "verification"
    ].copy()
    original_methods = original_verification["methods"].copy()

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = (
        config_with_new_verification_fields
    )
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=True)

        assert result.success is True

        # Verify verification section was not modified
        current_verification = config_with_new_verification_fields["state"][
            "verification"
        ]
        assert (
            current_verification["passed"] == original_verification["passed"]
        )
        assert (
            current_verification["overall_passed"]
            == original_verification["overall_passed"]
        )
        assert (
            current_verification["actual_method"]
            == original_verification["actual_method"]
        )
        assert current_verification["methods"] == original_methods


@pytest.mark.asyncio
async def test_remove_with_checksum_file_verification_succeeds(global_config):
    """Remove should succeed when app has checksum_file verification.

    Task 5.1: Tests removal with checksum_file verification method
    to ensure schema compatibility.
    """
    app_config = {
        "config_version": "2.0.0",
        "metadata": {"name": "test_app", "display_name": "Test App"},
        "source": {
            "type": "github",
            "owner": "test-owner",
            "repo": "test-repo",
            "prerelease": False,
        },
        "state": {
            "version": "2.0.0",
            "installed_date": "2024-02-01T12:00:00",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "checksum_file",
                "methods": [
                    {
                        "type": "checksum_file",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "abc123",
                        "computed": "abc123",
                        "source": "SHA256SUMS.txt",
                        "filename": "test_app.AppImage",
                    }
                ],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_remove_with_skip_verification_succeeds(global_config):
    """Remove should succeed when app has skip verification.

    Task 5.1: Tests removal with skip verification method
    to ensure schema compatibility.
    """
    app_config = {
        "config_version": "2.0.0",
        "metadata": {"name": "test_app", "display_name": "Test App"},
        "source": {
            "type": "github",
            "owner": "test-owner",
            "repo": "test-repo",
            "prerelease": False,
        },
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "skip",
                "warning": "No hash available for verification",
                "methods": [{"type": "skip", "status": "skipped"}],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_remove_with_legacy_verification_succeeds(global_config):
    """Remove should succeed when app has legacy verification format.

    Task 5.1: Tests removal with minimal verification format (only passed
    and methods) to ensure backward compatibility.
    """
    app_config = {
        "config_version": "2.0.0",
        "metadata": {"name": "test_app", "display_name": "Test App"},
        "source": {
            "type": "github",
            "owner": "test-owner",
            "repo": "test-repo",
            "prerelease": False,
        },
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "methods": [{"type": "skip", "status": "skipped"}],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_remove_with_keep_config_preserves_verification(
    global_config, config_with_new_verification_fields
):
    """Remove with keep_config=True should preserve verification in config.

    Task 5.1: When keep_config=True, the app config (including verification)
    should remain intact after removal.
    """
    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = (
        config_with_new_verification_fields
    )
    mock_config_manager.remove_app_config = MagicMock()

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=True)

        assert result.success is True
        assert result.config_removed is False
        # remove_app_config should NOT be called when keep_config=True
        mock_config_manager.remove_app_config.assert_not_called()


# ============================================================================
# Task 5.2: Tests for remove on apps with new verification format
# These tests verify schema validation works correctly with new verification
# fields when removing apps that were installed with the updated format.
# ============================================================================


@pytest.fixture
def config_with_all_new_verification_fields():
    """App config with all new verification fields populated.

    Includes: overall_passed, actual_method, warning (string), and digest.
    """
    return {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "2.0.0",
            "installed_date": "2024-02-01T12:00:00.000000",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "digest",
                "warning": "Hash verified using GitHub API digest",
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "abc123def456789",
                        "computed": "abc123def456789",
                        "source": "github_api",
                        "digest": "sha256:abc123def456789",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/mock/icons/test_app.png",
            },
        },
    }


@pytest.mark.asyncio
async def test_remove_app_schema_validation_with_new_fields(
    global_config, config_with_all_new_verification_fields
):
    """Remove should succeed with schema-valid new verification fields.

    Task 5.2: Verifies that app configs with new verification fields
    (overall_passed, actual_method, warning, digest) pass schema validation
    during removal.
    """

    # First, validate the config passes schema validation
    validate_app_state(config_with_all_new_verification_fields, "test_app")

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = (
        config_with_all_new_verification_fields
    )
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_remove_app_with_warning_null(global_config):
    """Remove should succeed when verification has warning: null.

    Task 5.2: The warning field can be null or a string. This tests
    the null case which is common when verification completes without issues.
    """
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00.000000",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "digest",
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                    }
                ],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    # Schema validation should pass (warning field is optional)
    validate_app_state(app_config, "test_app")

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)
        assert result.success is True


@pytest.mark.asyncio
async def test_remove_app_with_warning_string(global_config):
    """Remove should succeed when verification has warning as string.

    Task 5.2: Tests the warning field with an actual warning message.
    """
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00.000000",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "checksum_file",
                "warning": "Checksum file fallback, API digest unavailable",
                "methods": [
                    {
                        "type": "checksum_file",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "fedcba987654321",
                        "computed": "fedcba987654321",
                        "source": "SHA256SUMS.txt",
                        "filename": "test_app.AppImage",
                    }
                ],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    validate_app_state(app_config, "test_app")

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    service = RemoveService(mock_config_manager, global_config)

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)
        assert result.success is True


@pytest.mark.asyncio
async def test_remove_app_with_digest_field_in_method(global_config):
    """Remove should succeed when method has digest field.

    Task 5.2: The digest field in method items is an alternative to
    computed/expected fields. This tests schema compatibility.
    """

    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "3.0.0",
            "installed_date": "2024-03-01T15:30:00.000000",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "digest",
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha512",
                        "digest": "sha512:abcdef123456789abcdef",
                        "source": "github_api",
                    }
                ],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    validate_app_state(app_config, "test_app")

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    service = RemoveService(mock_config_manager, global_config)

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)
        assert result.success is True


@pytest.mark.asyncio
async def test_remove_app_with_multiple_verification_methods(global_config):
    """Remove should succeed with multiple verification methods.

    Task 5.2: Apps can have multiple verification methods recorded.
    This tests removal with both digest and checksum_file methods.
    """
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "4.0.0",
            "installed_date": "2024-04-01T00:00:00.000000",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "digest",
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "primary_hash_value",
                        "computed": "primary_hash_value",
                        "source": "github_api",
                    },
                    {
                        "type": "checksum_file",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "checksum_file_hash",
                        "computed": "checksum_file_hash",
                        "source": "SHA256SUMS.txt",
                        "filename": "test_app.AppImage",
                    },
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/mock/icons/test_app.png",
            },
        },
    }

    validate_app_state(app_config, "test_app")

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    mock_cache_manager = MagicMock()
    mock_cache_manager.clear_cache = AsyncMock()

    service = RemoveService(
        mock_config_manager, global_config, cache_manager=mock_cache_manager
    )

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)
        assert result.success is True
        assert result.config_removed is True


@pytest.mark.asyncio
async def test_remove_app_url_source_with_new_verification(global_config):
    """Remove should succeed for URL-sourced app with new verification.

    Task 5.2: URL-sourced apps have a different structure (overrides section).
    This tests removal with new verification fields on URL-sourced apps.
    """
    app_config = {
        "config_version": "2.0.0",
        "source": "url",
        "catalog_ref": None,
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-15T10:00:00.000000",
            "installed_path": "/mock/storage/custom_app.AppImage",
            "verification": {
                "passed": True,
                "overall_passed": True,
                "actual_method": "skip",
                "warning": "No verification method available for URL source",
                "methods": [{"type": "skip", "status": "skipped"}],
            },
            "icon": {"installed": False, "method": "none"},
        },
        "overrides": {
            "metadata": {
                "name": "custom_app",
                "display_name": "Custom App",
                "description": "",
            },
            "source": {
                "type": "github",
                "owner": "user",
                "repo": "custom",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "target_name": "custom_app",
                    "architectures": ["amd64"],
                }
            },
            "verification": {"method": "skip"},
            "icon": {"method": "extraction", "filename": "custom_app.png"},
        },
    }

    validate_app_state(app_config, "custom_app")

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    service = RemoveService(mock_config_manager, global_config)

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("custom_app", keep_config=False)
        assert result.success is True


@pytest.mark.asyncio
async def test_remove_app_failed_verification_with_new_fields(global_config):
    """Remove should succeed even when verification failed.

    Task 5.2: Apps with failed verification should still be removable.
    Tests that new verification fields work correctly in failure scenarios.
    """

    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "test_app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00.000000",
            "installed_path": "/mock/storage/test_app.AppImage",
            "verification": {
                "passed": False,
                "overall_passed": False,
                "actual_method": "digest",
                "warning": "Hash mismatch detected, app may be corrupted",
                "methods": [
                    {
                        "type": "digest",
                        "status": "failed",
                        "algorithm": "sha256",
                        "expected": "expected_hash_abc123",
                        "computed": "actual_hash_xyz789",
                        "source": "github_api",
                    }
                ],
            },
            "icon": {"installed": False, "method": "none"},
        },
    }

    validate_app_state(app_config, "test_app")

    mock_config_manager = MagicMock()
    mock_config_manager.load_app_config.return_value = app_config
    mock_config_manager.remove_app_config = MagicMock(return_value=True)

    service = RemoveService(mock_config_manager, global_config)

    with (
        patch("pathlib.Path.exists", autospec=True, return_value=True),
        patch("pathlib.Path.unlink", autospec=True),
        patch("shutil.rmtree"),
        patch("my_unicorn.core.desktop_entry.remove_desktop_entry_for_app"),
    ):
        result = await service.remove_app("test_app", keep_config=False)
        assert result.success is True
