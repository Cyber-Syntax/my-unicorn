"""Tests for ServiceContainer dependency injection.

This module tests the ServiceContainer class which manages service lifecycle
and dependency injection for CLI commands. Tests verify:
- Lazy initialization of services
- Singleton pattern (same instance returned each time)
- Factory methods create properly wired handlers
- Cleanup method closes resources
- ProgressReporter injection (both ProgressDisplay and NullProgressReporter)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.cli.container import ServiceContainer
from my_unicorn.config import ConfigManager
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)


class TestServiceContainerInitialization:
    """Tests for ServiceContainer constructor and default behavior."""

    def test_container_accepts_config_manager(self) -> None:
        """Container should accept a ConfigManager instance."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert container.config is config

    def test_container_accepts_progress_reporter(self) -> None:
        """Container should accept a ProgressReporter instance."""
        config = MagicMock(spec=ConfigManager)
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        assert container.progress is progress

    def test_container_creates_default_config_manager(self) -> None:
        """Container creates default ConfigManager when not provided."""
        with patch.object(ConfigManager, "__init__", return_value=None):
            container = ServiceContainer()

        assert isinstance(container.config, ConfigManager)

    def test_container_uses_null_reporter_when_not_provided(self) -> None:
        """Container uses NullProgressReporter when not provided."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert isinstance(container.progress, NullProgressReporter)

    def test_container_services_are_initially_none(self) -> None:
        """All lazy-loaded services should be None initially."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert container._session is None
        assert container._auth_manager is None
        assert container._cache_manager is None
        assert container._file_ops is None
        assert container._download_service is None
        assert container._verification_service is None
        assert container._icon_extractor is None
        assert container._github_client is None
        assert container._post_download_processor is None
        assert container._backup_service is None
        assert container._remove_service is None


class TestLazyInitialization:
    """Tests for lazy initialization of services."""

    def test_session_created_on_first_access(self) -> None:
        """HTTP session should be created only on first access."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert container._session is None

        with patch(
            "my_unicorn.cli.container.aiohttp.ClientSession"
        ) as mock_session:
            mock_session.return_value = MagicMock()
            _ = container.session

        assert container._session is not None

    def test_auth_manager_created_on_first_access(self) -> None:
        """Auth manager should be created only on first access."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert container._auth_manager is None

        with patch(
            "my_unicorn.cli.container.GitHubAuthManager.create_default"
        ) as mock_auth:
            mock_auth.return_value = MagicMock()
            _ = container.auth_manager

        assert container._auth_manager is not None

    def test_cache_manager_created_on_first_access(self) -> None:
        """Cache manager should be created only on first access."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert container._cache_manager is None

        with patch(
            "my_unicorn.cli.container.ReleaseCacheManager"
        ) as mock_cache:
            mock_cache.return_value = MagicMock()
            _ = container.cache_manager

        assert container._cache_manager is not None

    def test_file_ops_created_on_first_access(self) -> None:
        """File operations should be created only on first access."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        assert container._file_ops is None

        with patch("my_unicorn.cli.container.FileOperations") as mock_ops:
            mock_ops.return_value = MagicMock()
            _ = container.file_ops

        assert container._file_ops is not None

    def test_download_service_created_on_first_access(self) -> None:
        """Download service should be created only on first access."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        assert container._download_service is None

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService") as mock_dl,
        ):
            mock_dl.return_value = MagicMock()
            _ = container.download_service

        assert container._download_service is not None


class TestSingletonBehavior:
    """Tests for singleton pattern - same instance returned each time."""

    def test_session_returns_same_instance(self) -> None:
        """Session property returns the same instance on repeated calls."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        with patch(
            "my_unicorn.cli.container.aiohttp.ClientSession"
        ) as mock_session:
            mock_instance = MagicMock()
            mock_session.return_value = mock_instance

            first_access = container.session
            second_access = container.session

        assert first_access is second_access
        mock_session.assert_called_once()

    def test_auth_manager_returns_same_instance(self) -> None:
        """Auth manager returns the same instance on repeated calls."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        with patch(
            "my_unicorn.cli.container.GitHubAuthManager.create_default"
        ) as mock_auth:
            mock_instance = MagicMock()
            mock_auth.return_value = mock_instance

            first_access = container.auth_manager
            second_access = container.auth_manager

        assert first_access is second_access
        mock_auth.assert_called_once()

    def test_cache_manager_returns_same_instance(self) -> None:
        """Cache manager returns the same instance on repeated calls."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        with patch(
            "my_unicorn.cli.container.ReleaseCacheManager"
        ) as mock_cache:
            mock_instance = MagicMock()
            mock_cache.return_value = mock_instance

            first_access = container.cache_manager
            second_access = container.cache_manager

        assert first_access is second_access
        mock_cache.assert_called_once()

    def test_download_service_returns_same_instance(self) -> None:
        """Download service returns the same instance on repeated calls."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService") as mock_dl,
        ):
            mock_instance = MagicMock()
            mock_dl.return_value = mock_instance

            first_access = container.download_service
            second_access = container.download_service

        assert first_access is second_access
        mock_dl.assert_called_once()

    def test_github_client_returns_same_instance(self) -> None:
        """GitHub client returns the same instance on repeated calls."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.GitHubClient") as mock_github,
        ):
            mock_instance = MagicMock()
            mock_github.return_value = mock_instance

            first_access = container.github_client
            second_access = container.github_client

        assert first_access is second_access
        mock_github.assert_called_once()


class TestFactoryMethods:
    """Tests for factory methods that create workflow handlers."""

    def test_create_install_handler_returns_handler(self) -> None:
        """create_install_handler returns an InstallHandler instance."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService"),
            patch("my_unicorn.cli.container.FileOperations"),
            patch("my_unicorn.cli.container.GitHubClient"),
            patch("my_unicorn.cli.container.VerificationService"),
            patch("my_unicorn.cli.container.BackupService"),
            patch("my_unicorn.cli.container.PostDownloadProcessor"),
            patch("my_unicorn.cli.container.InstallHandler") as mock_handler,
        ):
            mock_instance = MagicMock()
            mock_handler.return_value = mock_instance

            handler = container.create_install_handler()

        assert handler is mock_instance
        mock_handler.assert_called_once()

    def test_create_install_handler_injects_progress(self) -> None:
        """create_install_handler injects the progress reporter."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService"),
            patch("my_unicorn.cli.container.FileOperations"),
            patch("my_unicorn.cli.container.GitHubClient"),
            patch("my_unicorn.cli.container.VerificationService"),
            patch("my_unicorn.cli.container.BackupService"),
            patch("my_unicorn.cli.container.PostDownloadProcessor"),
            patch("my_unicorn.cli.container.InstallHandler") as mock_handler,
        ):
            container.create_install_handler()

        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["progress_reporter"] is progress

    def test_create_install_app_service_returns_service(self) -> None:
        """create_install_application_service returns the service."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.GitHubClient"),
            patch(
                "my_unicorn.cli.container.InstallApplicationService"
            ) as mock_svc,
        ):
            mock_instance = MagicMock()
            mock_svc.return_value = mock_instance

            service = container.create_install_application_service()

        assert service is mock_instance
        mock_svc.assert_called_once()

    def test_create_update_manager_returns_manager(self) -> None:
        """create_update_manager returns an UpdateManager instance."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.UpdateManager") as mock_mgr,
        ):
            mock_instance = MagicMock()
            mock_mgr.return_value = mock_instance

            manager = container.create_update_manager()

        assert manager is mock_instance
        mock_mgr.assert_called_once()

    def test_create_update_manager_injects_progress(self) -> None:
        """create_update_manager injects the progress reporter."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.UpdateManager") as mock_mgr,
        ):
            container.create_update_manager()

        call_kwargs = mock_mgr.call_args.kwargs
        assert call_kwargs["progress_reporter"] is progress

    def test_create_update_app_service_returns_service(self) -> None:
        """create_update_application_service returns the service."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.UpdateManager"),
            patch(
                "my_unicorn.cli.container.UpdateApplicationService"
            ) as mock_svc,
        ):
            mock_instance = MagicMock()
            mock_svc.return_value = mock_instance

            service = container.create_update_application_service()

        assert service is mock_instance
        mock_svc.assert_called_once()

    def test_create_remove_service_returns_service(self) -> None:
        """create_remove_service returns the singleton RemoveService."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        with patch("my_unicorn.cli.container.RemoveService") as mock_remove:
            mock_instance = MagicMock()
            mock_remove.return_value = mock_instance

            service = container.create_remove_service()

        assert service is mock_instance

    def test_create_remove_service_returns_singleton(self) -> None:
        """create_remove_service returns the same singleton instance."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        with patch("my_unicorn.cli.container.RemoveService") as mock_remove:
            mock_instance = MagicMock()
            mock_remove.return_value = mock_instance

            first = container.create_remove_service()
            second = container.create_remove_service()

        assert first is second
        mock_remove.assert_called_once()


class TestCleanup:
    """Tests for cleanup method that closes resources."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_session(self) -> None:
        """Cleanup should close the HTTP session."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        mock_session = AsyncMock()
        container._session = mock_session

        await container.cleanup()

        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_sets_session_to_none(self) -> None:
        """Cleanup should set session to None after closing."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        mock_session = AsyncMock()
        container._session = mock_session

        await container.cleanup()

        assert container._session is None

    @pytest.mark.asyncio
    async def test_cleanup_does_nothing_when_no_session(self) -> None:
        """Cleanup should not raise if session was never created."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert container._session is None

        await container.cleanup()

        assert container._session is None

    @pytest.mark.asyncio
    async def test_cleanup_can_be_called_multiple_times(self) -> None:
        """Cleanup should be idempotent - safe to call multiple times."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        mock_session = AsyncMock()
        container._session = mock_session

        await container.cleanup()
        await container.cleanup()

        mock_session.close.assert_awaited_once()


class TestProgressReporterInjection:
    """Tests for ProgressReporter injection into services."""

    def test_download_service_receives_progress_reporter(self) -> None:
        """DownloadService receives the injected progress reporter."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService") as mock_dl,
        ):
            _ = container.download_service

        call_kwargs = mock_dl.call_args.kwargs
        assert call_kwargs["progress_reporter"] is progress

    def test_verification_service_receives_progress_reporter(self) -> None:
        """VerificationService receives the injected progress reporter."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService"),
            patch(
                "my_unicorn.cli.container.VerificationService"
            ) as mock_verify,
        ):
            _ = container.verification_service

        call_kwargs = mock_verify.call_args.kwargs
        assert call_kwargs["progress_reporter"] is progress

    def test_github_client_receives_progress_reporter(self) -> None:
        """GitHubClient receives the injected progress reporter."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.GitHubClient") as mock_github,
        ):
            _ = container.github_client

        call_kwargs = mock_github.call_args.kwargs
        assert call_kwargs["progress_reporter"] is progress

    def test_post_download_processor_receives_progress_reporter(self) -> None:
        """PostDownloadProcessor receives the injected progress reporter."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        progress = MagicMock(spec=ProgressReporter)
        container = ServiceContainer(
            config_manager=config, progress_reporter=progress
        )

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService"),
            patch("my_unicorn.cli.container.FileOperations"),
            patch("my_unicorn.cli.container.VerificationService"),
            patch("my_unicorn.cli.container.BackupService"),
            patch(
                "my_unicorn.cli.container.PostDownloadProcessor"
            ) as mock_proc,
        ):
            _ = container.post_download_processor

        call_kwargs = mock_proc.call_args.kwargs
        assert call_kwargs["progress_reporter"] is progress


class TestNullProgressReporterDefault:
    """Tests for NullProgressReporter as default behavior."""

    def test_null_reporter_used_when_none_provided(self) -> None:
        """NullProgressReporter is used when no reporter is provided."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert isinstance(container.progress, NullProgressReporter)

    def test_null_reporter_is_active_returns_false(self) -> None:
        """NullProgressReporter.is_active() returns False."""
        config = MagicMock(spec=ConfigManager)
        container = ServiceContainer(config_manager=config)

        assert container.progress.is_active() is False

    def test_download_service_receives_null_reporter(self) -> None:
        """DownloadService receives NullProgressReporter when not provided."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        with (
            patch("my_unicorn.cli.container.aiohttp.ClientSession"),
            patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
            patch("my_unicorn.cli.container.DownloadService") as mock_dl,
        ):
            _ = container.download_service

        call_kwargs = mock_dl.call_args.kwargs
        reporter = call_kwargs["progress_reporter"]
        assert isinstance(reporter, NullProgressReporter)


class TestGlobalConfigCaching:
    """Tests for global configuration caching behavior."""

    def test_global_config_loaded_once(self) -> None:
        """Global config should be loaded once and cached."""
        config = MagicMock(spec=ConfigManager)
        config.load_global_config.return_value = {
            "directory": {"storage": MagicMock()}
        }
        container = ServiceContainer(config_manager=config)

        _ = container.global_config
        _ = container.global_config
        _ = container.global_config

        config.load_global_config.assert_called_once()

    def test_install_dir_from_global_config(self) -> None:
        """install_dir should return storage path from global config."""
        config = MagicMock(spec=ConfigManager)
        mock_path = MagicMock()
        config.load_global_config.return_value = {
            "directory": {"storage": mock_path}
        }
        container = ServiceContainer(config_manager=config)

        assert container.install_dir is mock_path
