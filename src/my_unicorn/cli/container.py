"""Dependency injection container for service wiring.

This module provides a ServiceContainer that centralizes service instantiation
and dependency injection for CLI commands. It manages the lifecycle of shared
resources like HTTP sessions and ensures services are properly wired together.

The container implements lazy initialization for all services, creating them
only when first accessed. This reduces startup time and memory usage when
only a subset of services is needed.

Usage:
    >>> from my_unicorn.cli.container import ServiceContainer
    >>> from my_unicorn.config import ConfigManager
    >>> from my_unicorn.core.protocols.progress import NullProgressReporter
    >>>
    >>> config = ConfigManager()
    >>> progress = NullProgressReporter()
    >>> container = ServiceContainer(config, progress)
    >>>
    >>> try:
    ...     workflow = container.create_install_handler()
    ...     await workflow.install_from_catalog("app_name")
    ... finally:
    ...     await container.cleanup()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.backup import BackupService
from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import GitHubClient
from my_unicorn.core.icon import AppImageIconExtractor
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.core.remove import RemoveService
from my_unicorn.core.verification import VerificationService
from my_unicorn.core.workflows.install import InstallHandler
from my_unicorn.core.workflows.post_download import PostDownloadProcessor
from my_unicorn.core.workflows.services.install_service import (
    InstallApplicationService,
)
from my_unicorn.core.workflows.services.update_service import (
    UpdateApplicationService,
)
from my_unicorn.core.workflows.update import UpdateManager
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from my_unicorn.types import GlobalConfig

logger = get_logger(__name__)


class ServiceContainer:
    """Container for managing service lifecycle and dependencies.

    Implements the dependency injection pattern to decouple service creation
    from usage. Ensures single instances (singletons) of services within a
    session and proper wiring of dependencies.

    All services are lazily initialized on first access, reducing startup
    overhead when only a subset of functionality is needed.

    Attributes:
        config: Configuration manager for accessing global and app settings.
        progress: Progress reporter for UI feedback during operations.

    Available Services (lazy-loaded singletons):
        - session: aiohttp.ClientSession for HTTP operations
        - auth_manager: GitHubAuthManager for API authentication
        - cache_manager: ReleaseCacheManager for release caching
        - file_ops: FileOperations for storage tasks
        - download_service: DownloadService for file downloads
        - verification_service: VerificationService for hash verification
        - icon_extractor: AppImageIconExtractor for icon extraction
        - github_client: GitHubClient for GitHub API calls
        - backup_service: BackupService for update backups
        - post_download_processor: PostDownloadProcessor for post-install
        - remove_service: RemoveService for app removal

    Factory Methods:
        - create_install_handler(): Creates fully wired InstallHandler
        - create_install_application_service(): Creates InstallAppService
        - create_update_manager(): Creates fully wired UpdateManager
        - create_update_application_service(): Creates UpdateAppService
        - create_remove_service(): Returns configured RemoveService

    Thread Safety:
        - Not thread-safe across multiple threads
        - Safe for concurrent use within a single asyncio event loop
        - Each CLI command execution should use its own container instance

    Example:
        >>> from my_unicorn.cli.container import ServiceContainer
        >>> from my_unicorn.config import ConfigManager
        >>> from my_unicorn.ui.progress import ProgressDisplay
        >>>
        >>> config = ConfigManager()
        >>> progress = ProgressDisplay()
        >>> container = ServiceContainer(config, progress)
        >>>
        >>> try:
        ...     # Get services directly
        ...     client = container.github_client
        ...     release = await client.get_latest_release("owner", "repo")
        ...
        ...     # Or use factory methods for workflows
        ...     handler = container.create_install_handler()
        ...     result = await handler.install_from_catalog("app_name")
        ... finally:
        ...     await container.cleanup()  # Always cleanup!

    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize container with required infrastructure.

        Args:
            config_manager: Configuration manager for accessing global and
                app-specific configuration. Creates default if not provided.
            progress_reporter: UI progress implementation injected from CLI.
                Uses NullProgressReporter if not provided.

        """
        self.config = config_manager or ConfigManager()
        self.progress = progress_reporter or NullProgressReporter()

        # Load global configuration once
        self._global_config: GlobalConfig | None = None

        # Lazy initialization of services - created on first access
        self._session: aiohttp.ClientSession | None = None
        self._auth_manager: GitHubAuthManager | None = None
        self._cache_manager: ReleaseCacheManager | None = None
        self._file_ops: FileOperations | None = None
        self._download_service: DownloadService | None = None
        self._verification_service: VerificationService | None = None
        self._icon_extractor: AppImageIconExtractor | None = None
        self._github_client: GitHubClient | None = None
        self._post_download_processor: PostDownloadProcessor | None = None
        self._backup_service: BackupService | None = None
        self._remove_service: RemoveService | None = None

    @property
    def global_config(self) -> GlobalConfig:
        """Global configuration (loaded once, cached).

        Returns:
            Global configuration dictionary with directory paths and settings.

        """
        if self._global_config is None:
            self._global_config = self.config.load_global_config()
        return self._global_config

    @property
    def install_dir(self) -> Path:
        """Installation directory for AppImages.

        Returns:
            Path to the directory where AppImages are installed.

        """
        return self.global_config["directory"]["storage"]

    @property
    def session(self) -> aiohttp.ClientSession:
        """HTTP session (singleton, lazy-loaded).

        Creates a new aiohttp.ClientSession on first access.
        The session is reused for all HTTP operations within the container.

        Returns:
            Shared HTTP client session.

        """
        if self._session is None:
            self._session = aiohttp.ClientSession()
            logger.debug("Created new HTTP session")
        return self._session

    @property
    def auth_manager(self) -> GitHubAuthManager:
        """GitHub authentication manager (singleton, lazy-loaded).

        Returns:
            Authentication manager for GitHub API requests.

        """
        if self._auth_manager is None:
            self._auth_manager = GitHubAuthManager.create_default()
        return self._auth_manager

    @property
    def cache_manager(self) -> ReleaseCacheManager:
        """Release cache manager (singleton, lazy-loaded).

        Returns:
            Cache manager for GitHub release data.

        """
        if self._cache_manager is None:
            self._cache_manager = ReleaseCacheManager(
                config_manager=self.config
            )
        return self._cache_manager

    @property
    def file_ops(self) -> FileOperations:
        """File operations utility (singleton, lazy-loaded).

        Returns:
            File operations service for storage tasks.

        """
        if self._file_ops is None:
            self._file_ops = FileOperations(self.install_dir)
        return self._file_ops

    @property
    def download_service(self) -> DownloadService:
        """File download service with progress tracking.

        Singleton, lazy-loaded on first access.

        Returns:
            Download service configured with session and progress reporter.

        """
        if self._download_service is None:
            self._download_service = DownloadService(
                session=self.session,
                progress_reporter=self.progress,
                auth_manager=self.auth_manager,
            )
        return self._download_service

    @property
    def verification_service(self) -> VerificationService:
        """Hash verification service (singleton, lazy-loaded).

        Returns:
            Verification service for AppImage integrity checks.

        """
        if self._verification_service is None:
            self._verification_service = VerificationService(
                download_service=self.download_service,
                progress_reporter=self.progress,
            )
        return self._verification_service

    @property
    def icon_extractor(self) -> AppImageIconExtractor:
        """Icon extractor for AppImages (singleton, lazy-loaded).

        Returns:
            Icon extractor for extracting icons from AppImage files.

        """
        if self._icon_extractor is None:
            self._icon_extractor = AppImageIconExtractor()
        return self._icon_extractor

    @property
    def github_client(self) -> GitHubClient:
        """GitHub API client (singleton, lazy-loaded).

        Returns:
            GitHub client for release operations.

        """
        if self._github_client is None:
            self._github_client = GitHubClient(
                session=self.session,
                auth_manager=self.auth_manager,
                cache_manager=self.cache_manager,
                progress_reporter=self.progress,
            )
        return self._github_client

    @property
    def backup_service(self) -> BackupService:
        """Backup service (singleton, lazy-loaded).

        Returns:
            Service for backup operations during updates.

        """
        if self._backup_service is None:
            self._backup_service = BackupService(
                config_manager=self.config,
                global_config=self.global_config,
            )
        return self._backup_service

    @property
    def post_download_processor(self) -> PostDownloadProcessor:
        """Post-download processor (singleton, lazy-loaded).

        Returns:
            Processor for post-download operations.

        """
        if self._post_download_processor is None:
            self._post_download_processor = PostDownloadProcessor(
                download_service=self.download_service,
                storage_service=self.file_ops,
                config_manager=self.config,
                verification_service=self.verification_service,
                backup_service=self.backup_service,
                progress_reporter=self.progress,
            )
        return self._post_download_processor

    @property
    def remove_service(self) -> RemoveService:
        """Remove service (singleton, lazy-loaded).

        Returns:
            Service for removing installed applications.

        """
        if self._remove_service is None:
            self._remove_service = RemoveService(
                config_manager=self.config,
                global_config=self.global_config,
            )
        return self._remove_service

    def create_install_handler(self) -> InstallHandler:
        """Create install handler with all dependencies injected.

        Factory method that creates a fully wired InstallHandler ready for
        executing install operations.

        Returns:
            Configured InstallHandler instance.

        """
        return InstallHandler(
            download_service=self.download_service,
            storage_service=self.file_ops,
            config_manager=self.config,
            github_client=self.github_client,
            post_download_processor=self.post_download_processor,
            progress_reporter=self.progress,
        )

    def create_install_application_service(self) -> InstallApplicationService:
        """Create install application service with all dependencies injected.

        Factory method that creates a fully wired InstallApplicationService
        for executing complete installation workflows including target
        resolution, preflight checks, and progress management.

        Returns:
            Configured InstallApplicationService instance.

        """
        return InstallApplicationService(
            session=self.session,
            github_client=self.github_client,
            config_manager=self.config,
            install_dir=self.install_dir,
            progress_reporter=self.progress,
        )

    def create_update_manager(self) -> UpdateManager:
        """Create update manager with all dependencies injected.

        Factory method that creates a fully wired UpdateManager ready for
        executing update operations.

        Returns:
            Configured UpdateManager instance.

        """
        return UpdateManager(
            config_manager=self.config,
            auth_manager=self.auth_manager,
            progress_reporter=self.progress,
        )

    def create_update_application_service(self) -> UpdateApplicationService:
        """Create update application service with all dependencies injected.

        Factory method that creates a fully wired UpdateApplicationService
        for executing complete update workflows including target
        resolution, update checking, and progress management.

        Returns:
            Configured UpdateApplicationService instance.

        """
        return UpdateApplicationService(
            config_manager=self.config,
            update_manager=self.create_update_manager(),
            progress_reporter=self.progress,
        )

    def create_remove_service(self) -> RemoveService:
        """Create remove service with all dependencies injected.

        Factory method that creates a fully wired RemoveService ready for
        executing remove operations.

        Returns:
            Configured RemoveService instance.

        """
        return self.remove_service

    async def cleanup(self) -> None:
        """Clean up resources.

        Closes the HTTP session and any other resources that require explicit
        cleanup. This method should be called in a finally block to ensure
        resources are released even if an error occurs.

        Example:
            >>> container = ServiceContainer(config, progress)
            >>> try:
            ...     workflow = container.create_install_handler()
            ...     await workflow.install_from_catalog("app")
            ... finally:
            ...     await container.cleanup()

        """
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.debug("HTTP session closed")
