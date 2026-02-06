"""Update management for installed AppImage applications.

This module handles checking for updates, downloading new versions,
and managing the update process for installed AppImages.
"""

from __future__ import annotations

import asyncio

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.config.migration.helpers import warn_about_migration
from my_unicorn.constants import (
    ERROR_CONFIGURATION_MISSING,
    ERROR_UNEXPECTED,
    VERSION_UNKNOWN,
)
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.backup import BackupService
from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import Release, ReleaseFetcher, get_github_config
from my_unicorn.core.post_download import PostDownloadProcessor
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.core.update.catalog_cache import CatalogCache
from my_unicorn.core.update.context import prepare_update_context
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.core.update.workflows import (
    update_cached_progress,
    update_multiple_apps,
    update_single_app,
)
from my_unicorn.core.verification import VerificationService
from my_unicorn.exceptions import ConfigurationError
from my_unicorn.logger import get_logger
from my_unicorn.utils.version_utils import compare_versions

logger = get_logger(__name__)


class UpdateManager:
    r"""Manages updates for installed AppImage applications.

    Provides functionality to check for updates, download new versions,
    and manage the update process for installed AppImages. Supports both
    single app updates and batch update operations.

    Attributes:
        config_manager: Configuration manager for app settings.
        global_config: Global configuration dictionary.
        auth_manager: GitHub authentication manager.
        storage_service: File operations service.
        backup_service: Backup service for pre-update backups.
        progress_reporter: Progress reporter for tracking updates.
        verification_service: Hash verification service (on demand).
        post_download_processor: Post-download processor (on demand).
        _shared_api_task_id: Shared API task ID for progress tracking.
        _catalog_cache: In-memory cache for catalog entries.

    Thread Safety:
        - Safe for concurrent access across multiple asyncio tasks
        - Catalog cache is protected by asyncio.Lock for concurrent access
        - Each update operation should use a separate UpdateManager instance
          for isolated progress tracking
        - Shared verification service is initialized per-session and is
          thread-safe

    In-Memory Caching:
        - Catalog entries are cached in _catalog_cache during update session
        - Cache is cleared when UpdateManager instance is destroyed
        - Cache reduces redundant file I/O for multiple apps from catalog

    Example:
        >>> from my_unicorn.cli.container import ServiceContainer
        >>> container = ServiceContainer(config, progress)
        >>> try:
        ...     manager = container.create_update_manager()
        ...     updates = await manager.check_updates()
        ...     for info in updates:
        ...         if info.has_update:
        ...             print(f"{info.app_name}: {info.current_version}")
        ... finally:
        ...     await container.cleanup()

    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        auth_manager: GitHubAuthManager | None = None,
        cache_manager: ReleaseCacheManager | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize update manager.

        Args:
            config_manager: Configuration manager instance
            auth_manager: GitHub authentication manager instance
            cache_manager: Optional release cache manager instance
            progress_reporter: Optional progress reporter for tracking updates

        """
        self.config_manager = config_manager or ConfigManager()
        self.global_config = self.config_manager.load_global_config()
        self.auth_manager = auth_manager or GitHubAuthManager.create_default()
        self.cache_manager = cache_manager or ReleaseCacheManager(
            self.config_manager, ttl_hours=24
        )

        # Initialize storage service with install directory
        storage_dir = self.global_config["directory"]["storage"]
        self.storage_service = FileOperations(storage_dir)

        # Initialize backup service
        self.backup_service = BackupService(
            self.config_manager, self.global_config
        )

        # Apply null object pattern for progress reporter
        self.progress_reporter = progress_reporter or NullProgressReporter()

        # Initialize shared services - will be set when session is available
        self.verification_service: VerificationService | None = None
        self.post_download_processor: PostDownloadProcessor | None = None

        # In-memory catalog cache for current update session
        self._catalog_cache = CatalogCache(self.config_manager)

        # Shared API task ID for progress tracking across update operations
        self._shared_api_task_id: str | None = None

    @classmethod
    def create_default(
        cls,
        config_manager: ConfigManager | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> UpdateManager:
        """Create UpdateManager with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            config_manager: Optional configuration manager
                (creates new if None)
            progress_reporter: Optional progress reporter for tracking

        Returns:
            Configured UpdateManager instance

        """
        return cls(
            config_manager=config_manager,
            progress_reporter=progress_reporter,
        )

    def _initialize_services(self, session: aiohttp.ClientSession) -> None:
        """Initialize shared services with HTTP session.

        Args:
            session: aiohttp session for downloads

        """
        download_service = DownloadService(session, self.progress_reporter)
        # Get progress reporter from download service
        progress_reporter = download_service.progress_reporter
        self.verification_service = VerificationService(
            download_service,
            progress_reporter,
            cache_manager=self.cache_manager,
        )

        # Initialize post-download processor
        self.post_download_processor = PostDownloadProcessor(
            download_service=download_service,
            storage_service=self.storage_service,
            config_manager=self.config_manager,
            verification_service=self.verification_service,
            backup_service=self.backup_service,
            progress_reporter=self.progress_reporter,
        )

    async def _fetch_release_data(
        self,
        owner: str,
        repo: str,
        should_use_prerelease: bool,
        session: aiohttp.ClientSession,
        refresh_cache: bool,
    ) -> Release:
        """Fetch release data from GitHub.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            should_use_prerelease: Whether to prefer prerelease
            session: aiohttp session
            refresh_cache: Whether to bypass cache

        Returns:
            Release data

        Raises:
            ValueError: If no releases found
            aiohttp.ClientError: If API request fails

        """
        fetcher = ReleaseFetcher(
            owner,
            repo,
            session,
            cache_manager=self.cache_manager,
            auth_manager=self.auth_manager,
        )
        if should_use_prerelease:
            logger.debug("Fetching latest prerelease for %s/%s", owner, repo)
            try:
                return await fetcher.fetch_latest_prerelease(
                    ignore_cache=refresh_cache
                )
            except ValueError as e:
                if "No prereleases found" in str(e):
                    logger.warning(
                        "No prereleases found for %s/%s, "
                        "falling back to latest release",
                        owner,
                        repo,
                    )
                    return await fetcher.fetch_latest_release_or_prerelease(
                        prefer_prerelease=False,
                        ignore_cache=refresh_cache,
                    )
                raise
        return await fetcher.fetch_latest_release_or_prerelease(
            prefer_prerelease=False, ignore_cache=refresh_cache
        )

    async def _build_update_info(
        self,
        app_name: str,
        app_config: dict[str, object],
        release_data: Release,
    ) -> UpdateInfo:
        """Build UpdateInfo from app config and release data.

        Args:
            app_name: Name of the app
            app_config: App configuration
            release_data: Release data from GitHub

        Returns:
            UpdateInfo object with update status

        """
        current_version = app_config.get("state", {}).get(
            "version", VERSION_UNKNOWN
        )
        github_config = get_github_config(app_config)
        owner = github_config.owner
        repo = github_config.repo

        latest_version = release_data.version
        has_update = compare_versions(current_version, latest_version)

        return UpdateInfo(
            app_name=app_name,
            current_version=current_version,
            latest_version=latest_version,
            has_update=has_update,
            release_url=f"https://github.com/{owner}/{repo}/releases/tag/{latest_version}",
            prerelease=release_data.prerelease,
            original_tag_name=release_data.original_tag_name
            or f"v{latest_version}",
            release_data=release_data,
            app_config=app_config,
        )

    async def check_single_update(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        refresh_cache: bool = False,
    ) -> UpdateInfo:
        """Check for updates for a single app.

        Args:
            app_name: Name of the app to check
            session: aiohttp session
            refresh_cache: If True, bypass cache and fetch fresh data from API

        Returns:
            UpdateInfo object with error_reason set if check failed.
            Never raises - all errors are captured in UpdateInfo.error_reason.

        Note:
            This method catches all exceptions and returns them as error
            reasons in the UpdateInfo object. It never raises exceptions to
            ensure partial success in batch update checks.

        """
        try:
            # Load app config
            app_config = self._load_app_config_or_fail(
                app_name, "check_update"
            )

            # Extract config values
            github_config = get_github_config(app_config)
            owner = github_config.owner
            repo = github_config.repo
            should_use_prerelease = github_config.prerelease

            logger.debug(
                "Checking updates for %s (%s/%s)", app_name, owner, repo
            )

            # Fetch latest release
            release_data = await self._fetch_release_data(
                owner, repo, should_use_prerelease, session, refresh_cache
            )

            # Build and return update info
            return await self._build_update_info(
                app_name, app_config, release_data
            )

        except aiohttp.client_exceptions.ClientResponseError as e:
            # Handle HTTP errors (401, 403, 404, etc.)
            if e.status == 401:
                error_msg = "Authentication required - please set GitHub token"
                logger.exception(
                    "Failed to check updates for %s: Unauthorized (401). "
                    "Your GitHub Personal Access Token (PAT) is invalid. "
                    "Please set a valid token in your environment or "
                    "configuration.",
                    app_name,
                )
            else:
                error_msg = f"HTTP {e.status} error"
                logger.exception(
                    "Failed to check updates for %s: HTTP %d - %s",
                    app_name,
                    e.status,
                    e.message,
                )
            return UpdateInfo.create_error(app_name, error_msg)

        except (ConfigurationError, ValueError) as e:
            # Handle config and validation errors
            logger.exception("Failed to check updates for %s", app_name)
            return UpdateInfo.create_error(app_name, str(e))

        except Exception as e:
            # Catch-all for unexpected errors
            logger.exception("Failed to check updates for %s", app_name)
            return UpdateInfo.create_error(
                app_name, ERROR_UNEXPECTED.format(error=e)
            )

    async def check_updates(
        self,
        app_names: list[str] | None = None,
        refresh_cache: bool = False,
    ) -> list[UpdateInfo]:
        """Check for updates for all or specified apps.

        Args:
            app_names: List of app names to check, or None for all installed
                apps
            refresh_cache: If True, bypass cache and fetch fresh data from
                API

        Returns:
            List of UpdateInfo objects, one per app. Errors are captured in
            individual UpdateInfo.error_reason fields rather than raising.

        Note:
            This method catches all exceptions per-app to ensure partial
            success. Individual app failures are returned as UpdateInfo
            objects with error_reason set.

        """
        warn_about_migration(self.config_manager)

        if app_names is None:
            app_names = self.config_manager.list_installed_apps()

        if not app_names:
            logger.info("No installed apps found")
            return []

        logger.info("🔄 Checking %d app(s) for updates...", len(app_names))

        async with aiohttp.ClientSession() as session:
            tasks = [
                self.check_single_update(
                    app, session, refresh_cache=refresh_cache
                )
                for app in app_names
            ]
            return await asyncio.gather(*tasks)

    def _load_app_config_or_fail(
        self, app_name: str, context: str = ""
    ) -> dict[str, object]:
        """Load app config with consistent error handling.

        Centralizes config loading logic to eliminate duplication and
        ensure consistent error messages across all call sites.

        Args:
            app_name: Name of app to load config for
            context: Optional context for error message
                (e.g., "check_update", "prepare_update")

        Returns:
            App configuration dictionary (merged effective config)

        Raises:
            ConfigurationError: If config not found or invalid

        Example:
            config = self._load_app_config_or_fail("qownnotes", "update_check")

        """
        config = self.config_manager.load_app_config(app_name)
        if not config:
            prefix = f"{context}: " if context else ""
            msg = (
                f"{prefix}"
                f"{ERROR_CONFIGURATION_MISSING.format(app_name=app_name)}"
            )
            raise ConfigurationError(msg)
        return config

    async def update_single_app(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        force: bool = False,
        update_info: UpdateInfo | None = None,
    ) -> tuple[bool, str | None]:
        """Update a single app.

        Args:
            app_name: Name of the app to update
            session: aiohttp session
            force: Force update even if no new version available
            update_info: Optional pre-fetched update info with
                cached release data

        Returns:
            Tuple of (success status, error reason or None)

        """
        # Initialize session-dependent services if not already done
        if self.post_download_processor is None:
            self._initialize_services(session)

        # Prepare context preparation function with bound dependencies
        async def prepare_context_func(
            app_name: str,
            session: aiohttp.ClientSession,
            force: bool,
            update_info: UpdateInfo | None,
        ) -> tuple[dict[str, object] | None, str | None]:
            return await prepare_update_context(
                app_name,
                session,
                force,
                update_info,
                self.check_single_update,
                self._load_app_config_or_fail,
                self._catalog_cache.load_catalog,
            )

        return await update_single_app(
            app_name,
            session,
            force,
            update_info,
            self.global_config,
            prepare_context_func,
            self.backup_service,
            self.post_download_processor,
        )

    async def update_multiple_apps(
        self,
        app_names: list[str],
        force: bool = False,
        update_infos: list[UpdateInfo] | None = None,
        api_task_id: str | None = None,
    ) -> tuple[dict[str, bool], dict[str, str]]:
        """Update multiple apps.

        Args:
            app_names: List of app names to update
            force: Force update even if no new version available
            update_infos: Optional pre-fetched update info objects with cached
                release data
            api_task_id: Optional API progress task ID for tracking

        Returns:
            Tuple of (success status dict, error reasons dict)

        """
        # Set shared API task ID for progress tracking
        if api_task_id:
            self._shared_api_task_id = api_task_id

        return await update_multiple_apps(
            app_names,
            force,
            update_infos,
            api_task_id,
            self.global_config,
            self.update_single_app,
            update_cached_progress,
            self.progress_reporter,
        )
