"""Integration tests for RemoveService.remove_app method.

Tests the main entry point and orchestration of removal operations.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.core.remove import RemoveService
from my_unicorn.types import AppStateConfig, GlobalConfig


class TestRemoveAppSuccess:
    """Tests for successful removal scenarios."""

    @pytest.mark.asyncio
    async def test_successful_removal_all_components(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should successfully remove all components when they exist."""
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("shutil.rmtree"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            assert result.success is True
            assert result.app_name == "test-app"
            assert result.config_removed is True
            assert result.icon_removed is True
            assert result.desktop_entry_removed is True
            assert result.cache_cleared is True
            assert result.cache_owner == "test-owner"
            assert result.cache_repo == "test-repo"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_successful_removal_with_keep_config(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should keep config when keep_config=True."""
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("shutil.rmtree"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=True)

            assert result.success is True
            assert result.config_removed is False
            mock_config_manager.remove_app_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_removal_missing_components(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should handle gracefully when some components are missing."""
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=False,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            assert result.success is True
            assert result.app_name == "test-app"
            assert result.icon_removed is False
            assert result.desktop_entry_removed is False

    @pytest.mark.asyncio
    async def test_removal_without_backup_directory(
        self,
        mock_config_manager: MagicMock,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should handle gracefully when backup directory is not configured."""
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "icon": Path("/test/icons"),
            }
        }
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            assert result.success is True
            assert result.backup_removed is False
            assert result.backup_path is None

    @pytest.mark.asyncio
    async def test_removal_without_cache_info(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
    ) -> None:
        """Should handle gracefully when cache info is missing."""
        app_config = {
            "config_version": "2.0.0",
            "metadata": {"name": "test-app", "display_name": "Test App"},
            "source": {"type": "github"},
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00Z",
                "installed_path": "/test/storage/test-app.AppImage",
                "verification": {"passed": True, "methods": []},
            },
        }
        mock_config_manager.load_app_config.return_value = app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("shutil.rmtree"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            assert result.success is True
            assert result.cache_cleared is False
            assert result.cache_owner is None
            assert result.cache_repo is None
            mock_cache_manager.clear_cache.assert_not_called()


class TestRemoveAppFailure:
    """Tests for failure scenarios."""

    @pytest.mark.asyncio
    async def test_app_not_found(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
    ) -> None:
        """Should return error when app config is not found."""
        mock_config_manager.load_app_config.return_value = None
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        result = await service.remove_app("missing-app", keep_config=False)

        assert result.success is False
        assert result.app_name == "missing-app"
        assert result.error == "App 'missing-app' not found"
        assert result.removed_files == []
        assert result.config_removed is False

    @pytest.mark.asyncio
    async def test_exception_during_load_config(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
    ) -> None:
        """Should handle exceptions during config loading gracefully."""
        mock_config_manager.load_app_config.side_effect = RuntimeError(
            "Config error"
        )
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        result = await service.remove_app("test-app", keep_config=False)

        assert result.success is False
        assert result.app_name == "test-app"
        assert result.error == "Removal operation failed"

    @pytest.mark.asyncio
    async def test_individual_operation_failures_do_not_fail_removal(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Individual operation failures should be logged but not fail removal.

        RemoveService handles operation failures gracefully - each operation
        logs warnings but the overall removal continues and succeeds.
        """
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with patch(
            "pathlib.Path.exists",
            side_effect=RuntimeError("Path error"),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            # Removal should succeed even with individual operation failures
            assert result.success is True
            assert result.app_name == "test-app"
            # Some operations will fail but others succeed (e.g., cache clear)
            assert result.cache_cleared is True


class TestRemovalResultConstruction:
    """Tests for RemovalResult construction and logging."""

    @pytest.mark.asyncio
    async def test_removed_files_list_populated(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should populate removed_files list correctly."""
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("shutil.rmtree"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            assert len(result.removed_files) > 0
            assert "/test/storage/test-app.AppImage" in result.removed_files

    @pytest.mark.asyncio
    async def test_backup_path_reported(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should report backup path in result."""
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("shutil.rmtree"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            assert result.backup_path == "/test/backups/test-app"

    @pytest.mark.asyncio
    async def test_icon_path_reported(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
    ) -> None:
        """Should report icon path in result."""
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("shutil.rmtree"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            result = await service.remove_app("test-app", keep_config=False)

            assert result.icon_path == "/test/icons/test-app.png"


class TestLoggingBehavior:
    """Tests for logging during removal operations."""

    @pytest.mark.asyncio
    async def test_logs_removal_results(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        sample_app_config: AppStateConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log removal results appropriately."""
        mock_config_manager.load_app_config.return_value = sample_app_config
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("shutil.rmtree"),
            patch(
                "my_unicorn.core.desktop_entry.remove_desktop_entry_for_app",
                return_value=True,
            ),
        ):
            await service.remove_app("test-app", keep_config=False)

            # Verify logging occurred (specific messages may vary)
            assert any(
                "test-app" in record.message for record in caplog.records
            )

    @pytest.mark.asyncio
    async def test_logs_error_when_app_not_found(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log error when app is not found."""
        mock_config_manager.load_app_config.return_value = None
        service = RemoveService(
            mock_config_manager, global_config, mock_cache_manager
        )

        await service.remove_app("missing-app", keep_config=False)

        assert any(
            "missing-app" in record.message
            and "not found" in record.message.lower()
            for record in caplog.records
        )
