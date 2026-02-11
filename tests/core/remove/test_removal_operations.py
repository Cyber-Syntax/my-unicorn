"""Unit tests for individual RemoveService operations.

Tests for private methods that perform specific removal tasks:
- _remove_appimage_files
- _clear_cache
- _remove_backups
- _remove_desktop_entry
- _remove_icon
- _remove_config
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.remove import RemoveService
from my_unicorn.types import AppStateConfig


class TestRemoveAppImageFiles:
    """Tests for _remove_appimage_files method."""

    def test_removes_existing_appimage(
        self, remove_service: RemoveService, sample_app_config: AppStateConfig
    ) -> None:
        """Should remove AppImage file when it exists."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink") as mock_unlink,
        ):
            result = remove_service._remove_appimage_files(sample_app_config)

            assert result.success is True
            assert len(result.files) == 1
            assert result.files[0] == "/test/storage/test-app.AppImage"
            mock_unlink.assert_called_once()

    def test_handles_missing_appimage(
        self, remove_service: RemoveService, sample_app_config: AppStateConfig
    ) -> None:
        """Should handle gracefully when AppImage file does not exist."""
        with patch("pathlib.Path.exists", return_value=False):
            result = remove_service._remove_appimage_files(sample_app_config)

            assert result.success is True
            assert result.files == []

    def test_handles_missing_installed_path(
        self, remove_service: RemoveService
    ) -> None:
        """Should handle config without installed_path."""
        config = {
            "state": {},
        }
        result = remove_service._remove_appimage_files(config)

        assert result.success is True
        assert result.files == []

    def test_handles_unlink_failure(
        self, remove_service: RemoveService, sample_app_config: AppStateConfig
    ) -> None:
        """Should handle unlink errors gracefully."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "pathlib.Path.unlink",
                side_effect=PermissionError("Access denied"),
            ),
        ):
            result = remove_service._remove_appimage_files(sample_app_config)

            assert result.success is False
            assert result.files == []


class TestClearCache:
    """Tests for _clear_cache method."""

    @pytest.mark.asyncio
    async def test_clears_cache_with_owner_repo(
        self,
        remove_service: RemoveService,
        sample_app_config: AppStateConfig,
        mock_cache_manager: MagicMock,
    ) -> None:
        """Should clear cache when owner and repo are present."""
        result = await remove_service._clear_cache(sample_app_config)

        assert result.success is True
        assert result.metadata["owner"] == "test-owner"
        assert result.metadata["repo"] == "test-repo"
        mock_cache_manager.clear_cache.assert_called_once_with(
            "test-owner", "test-repo"
        )

    @pytest.mark.asyncio
    async def test_skips_cache_without_owner(
        self, remove_service: RemoveService
    ) -> None:
        """Should skip cache clearing when owner is missing."""
        config = {
            "source": {
                "repo": "test-repo",
            }
        }
        result = await remove_service._clear_cache(config)

        assert result.success is True
        assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_skips_cache_without_repo(
        self, remove_service: RemoveService
    ) -> None:
        """Should skip cache clearing when repo is missing."""
        config = {
            "source": {
                "owner": "test-owner",
            }
        }
        result = await remove_service._clear_cache(config)

        assert result.success is True
        assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_handles_cache_clear_failure(
        self,
        remove_service: RemoveService,
        sample_app_config: AppStateConfig,
        mock_cache_manager: MagicMock,
    ) -> None:
        """Should handle cache clearing errors gracefully."""
        mock_cache_manager.clear_cache.side_effect = RuntimeError(
            "Cache error"
        )

        result = await remove_service._clear_cache(sample_app_config)

        assert result.success is False
        assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_creates_cache_manager_if_none(
        self,
        mock_config_manager: MagicMock,
        global_config: dict,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should create ReleaseCacheManager if not provided."""
        service = RemoveService(
            config_manager=mock_config_manager,
            global_config=global_config,
            cache_manager=None,
        )

        with patch(
            "my_unicorn.core.remove.ReleaseCacheManager"
        ) as mock_cache_class:
            mock_instance = MagicMock()
            mock_instance.clear_cache = AsyncMock()
            mock_cache_class.return_value = mock_instance

            result = await service._clear_cache(sample_app_config)

            assert result.success is True
            mock_cache_class.assert_called_once_with(mock_config_manager)
            mock_instance.clear_cache.assert_called_once()


class TestRemoveBackups:
    """Tests for _remove_backups method."""

    def test_removes_backup_directory(
        self, remove_service: RemoveService
    ) -> None:
        """Should remove backup directory when it exists."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("shutil.rmtree") as mock_rmtree,
        ):
            result = remove_service._remove_backups("test-app")

            assert result.success is True
            assert len(result.files) == 1
            assert result.files[0] == "/test/backups/test-app"
            assert result.metadata["path"] == "/test/backups/test-app"
            mock_rmtree.assert_called_once()

    def test_handles_missing_backup_directory(
        self, remove_service: RemoveService
    ) -> None:
        """Should handle gracefully when backup directory does not exist."""
        with patch("pathlib.Path.exists", return_value=False):
            result = remove_service._remove_backups("test-app")

            assert result.success is True
            assert result.files == []
            assert result.metadata["path"] == "/test/backups/test-app"

    def test_handles_missing_backup_config(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Should handle gracefully when backup directory not configured."""
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "icon": Path("/test/icons"),
            }
        }
        service = RemoveService(
            config_manager=mock_config_manager, global_config=global_config
        )

        result = service._remove_backups("test-app")

        assert result.success is True
        assert result.files == []
        assert result.metadata == {}

    def test_handles_rmtree_failure(
        self, remove_service: RemoveService
    ) -> None:
        """Should handle rmtree errors gracefully."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "shutil.rmtree",
                side_effect=PermissionError("Access denied"),
            ),
        ):
            result = remove_service._remove_backups("test-app")

            assert result.success is False
            assert result.metadata == {}


class TestRemoveDesktopEntry:
    """Tests for _remove_desktop_entry method."""

    def test_removes_desktop_entry_successfully(
        self, remove_service: RemoveService, mock_config_manager: MagicMock
    ) -> None:
        """Should remove desktop entry when present."""
        with patch(
            "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
            return_value=True,
        ) as mock_remove:
            result = remove_service._remove_desktop_entry("test-app")

            assert result.success is True
            mock_remove.assert_called_once_with(
                "test-app", mock_config_manager
            )

    def test_handles_no_desktop_entry(
        self, remove_service: RemoveService, mock_config_manager: MagicMock
    ) -> None:
        """Should handle gracefully when no desktop entry exists."""
        with patch(
            "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
            return_value=False,
        ):
            result = remove_service._remove_desktop_entry("test-app")

            assert result.success is False

    def test_handles_desktop_entry_removal_failure(
        self, remove_service: RemoveService
    ) -> None:
        """Should handle desktop entry removal errors gracefully."""
        with patch(
            "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
            side_effect=RuntimeError("Desktop entry error"),
        ):
            result = remove_service._remove_desktop_entry("test-app")

            assert result.success is False


class TestRemoveIcon:
    """Tests for _remove_icon method."""

    def test_removes_existing_icon(
        self, remove_service: RemoveService, sample_app_config: AppStateConfig
    ) -> None:
        """Should remove icon file when it exists."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink") as mock_unlink,
        ):
            result = remove_service._remove_icon(sample_app_config)

            assert result.success is True
            assert len(result.files) == 1
            assert result.files[0] == "/test/icons/test-app.png"
            assert result.metadata["path"] == "/test/icons/test-app.png"
            mock_unlink.assert_called_once()

    def test_handles_missing_icon(
        self, remove_service: RemoveService, sample_app_config: AppStateConfig
    ) -> None:
        """Should handle gracefully when icon file does not exist."""
        with patch("pathlib.Path.exists", return_value=False):
            result = remove_service._remove_icon(sample_app_config)

            assert result.success is True
            assert result.files == []
            assert result.metadata["path"] == "/test/icons/test-app.png"

    def test_handles_missing_icon_path_in_config(
        self, remove_service: RemoveService
    ) -> None:
        """Should handle config without icon path."""
        config = {
            "state": {
                "icon": {},
            }
        }
        result = remove_service._remove_icon(config)

        assert result.success is True
        assert result.files == []
        assert result.metadata == {}

    def test_handles_missing_icon_section(
        self, remove_service: RemoveService
    ) -> None:
        """Should handle config without icon section."""
        config = {
            "state": {},
        }
        result = remove_service._remove_icon(config)

        assert result.success is True
        assert result.files == []
        assert result.metadata == {}

    def test_handles_icon_unlink_failure(
        self, remove_service: RemoveService, sample_app_config: AppStateConfig
    ) -> None:
        """Should handle icon unlink errors gracefully."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink", side_effect=OSError("Unlink failed")),
        ):
            result = remove_service._remove_icon(sample_app_config)

            assert result.success is False
            assert result.metadata == {}


class TestRemoveConfig:
    """Tests for _remove_config method."""

    def test_removes_config_successfully(
        self,
        remove_service: RemoveService,
        mock_config_manager: MagicMock,
    ) -> None:
        """Should remove app config when present."""
        mock_config_manager.remove_app_config.return_value = True

        result = remove_service._remove_config("test-app")

        assert result.success is True
        mock_config_manager.remove_app_config.assert_called_once_with(
            "test-app"
        )

    def test_handles_no_config_to_remove(
        self,
        remove_service: RemoveService,
        mock_config_manager: MagicMock,
    ) -> None:
        """Should handle gracefully when no config exists."""
        mock_config_manager.remove_app_config.return_value = False

        result = remove_service._remove_config("test-app")

        assert result.success is False

    def test_handles_config_removal_failure(
        self,
        remove_service: RemoveService,
        mock_config_manager: MagicMock,
    ) -> None:
        """Should handle config removal errors gracefully."""
        mock_config_manager.remove_app_config.side_effect = RuntimeError(
            "Config error"
        )

        result = remove_service._remove_config("test-app")

        assert result.success is False
