"""Update management for installed AppImage applications.

This module handles checking for updates, downloading new versions,
and managing the update process for installed AppImages.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.config.migration.helpers import warn_about_migration
from my_unicorn.constants import (
    ERROR_CATALOG_MISSING,
    ERROR_CONFIGURATION_MISSING,
    ERROR_UNEXPECTED,
    VERSION_UNKNOWN,
)
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.backup import BackupService
from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import (
    Asset,
    Release,
    ReleaseFetcher,
    get_github_config,
)
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.core.verification import VerificationService
from my_unicorn.core.workflows.post_download import (
    OperationType,
    PostDownloadContext,
    PostDownloadProcessor,
)
from my_unicorn.exceptions import (
    ConfigurationError,
    UpdateError,
    VerificationError,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_utils import select_best_appimage_asset
from my_unicorn.utils.download_utils import extract_filename_from_url
from my_unicorn.utils.version_utils import compare_versions

logger = get_logger(__name__)


@dataclass
class UpdateInfo:
    r"""Information about an available update for an installed application.

    This class encapsulates update status and metadata, including in-memory
    caching of release data and loaded config to eliminate redundant cache
    file reads during a single update operation.

    Attributes:
        app_name: Name of the application.
        current_version: Currently installed version string.
        latest_version: Latest available version from GitHub.
        has_update: True if latest_version is newer than current_version.
        release_url: URL to the GitHub release page.
        prerelease: True if the latest release is a prerelease.
        original_tag_name: Original Git tag name for the release.
        release_data: Cached Release object from GitHub API.
        app_config: Cached loaded application configuration.
        error_reason: Error message if update check failed, None on success.

    Example:
        >>> info = await manager.check_single_update("firefox", session)
        >>> if info.is_success and info.has_update:
        ...     print(f"Update: {info.current_version} -> {info.latest_version}")
        >>> elif info.error_reason:
        ...     print(f"Check failed: {info.error_reason}")

    """

    app_name: str
    current_version: str = VERSION_UNKNOWN
    latest_version: str = VERSION_UNKNOWN
    has_update: bool = False
    release_url: str = ""
    prerelease: bool = False
    original_tag_name: str = ""
    release_data: Release | None = None
    app_config: dict[str, Any] | None = None  # Cached loaded config
    error_reason: str | None = None

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        # Set default original_tag_name if not provided
        if (
            not self.original_tag_name
            and self.latest_version != VERSION_UNKNOWN
        ):
            self.original_tag_name = f"v{self.latest_version}"

    @classmethod
    def create_error(cls, app_name: str, reason: str) -> UpdateInfo:
        """Create an UpdateInfo representing an error condition.

        Args:
            app_name: Name of the application
            reason: Error reason/message

        Returns:
            UpdateInfo with error_reason set

        """
        return cls(app_name=app_name, error_reason=reason)

    @property
    def is_success(self) -> bool:
        """Check if update info represents a successful operation.

        Returns:
            True if no error occurred, False otherwise

        """
        return self.error_reason is None

    def __repr__(self) -> str:
        """String representation of update info."""
        if self.error_reason:
            return f"UpdateInfo({self.app_name}: Error - {self.error_reason})"
        status = "Available" if self.has_update else "Up to date"
        return (
            f"UpdateInfo({self.app_name}: {self.current_version} -> "
            f"{self.latest_version}, {status})"
        )


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
        _cache_lock: Async lock for thread-safe catalog cache access.

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
        # Cleared when UpdateManager instance is destroyed
        # Thread-safe with asyncio.Lock for concurrent access
        self._catalog_cache: dict[str, dict[str, Any] | None] = {}
        self._cache_lock = asyncio.Lock()
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
            config_manager: Optional configuration manager (creates new if None)
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
            download_service, progress_reporter
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
                        "No prereleases found for %s/%s, falling back to latest release",
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
        app_config: dict[str, Any],
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
                    "Please set a valid token in your environment or configuration.",
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
            update_infos = await asyncio.gather(*tasks)

        return update_infos

        return update_infos

    async def _load_catalog_if_needed(
        self, app_name: str, catalog_ref: str | None
    ) -> dict[str, Any] | None:
        """Load catalog entry if app references one.

        Args:
            app_name: Name of the app
            catalog_ref: Catalog reference from app config

        Returns:
            Catalog entry dict or None

        Raises:
            UpdateError: If catalog reference is invalid or not found

        """
        if not catalog_ref:
            return None

        try:
            return await self._load_catalog_cached(catalog_ref)
        except (FileNotFoundError, ValueError) as e:
            msg = ERROR_CATALOG_MISSING.format(
                app_name=app_name, catalog_ref=catalog_ref
            )
            raise UpdateError(
                message=msg,
                context={"app_name": app_name, "catalog_ref": catalog_ref},
                cause=e,
            ) from e

    async def _resolve_update_info(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        force: bool,
        update_info: UpdateInfo | None,
    ) -> tuple[UpdateInfo | None, str | None]:
        """Resolve update info by using cached or checking for updates.

        Args:
            app_name: Name of the app
            session: aiohttp session
            force: Force update even if no new version
            update_info: Optional pre-fetched update info

        Returns:
            Tuple of (UpdateInfo, error message). UpdateInfo is None on error.

        """
        # Use cached update info if provided, otherwise check for updates
        if not update_info:
            update_info = await self.check_single_update(app_name, session)

        # Check if update info indicates an error
        if not update_info.is_success:
            logger.error(
                "Failed to check updates for %s: %s",
                app_name,
                update_info.error_reason,
            )
            return None, update_info.error_reason or "Failed to check updates"

        # Check if update is needed (skip if up to date and not forced)
        if not update_info.has_update and not force:
            logger.info("%s is already up to date", app_name)
            return update_info, None  # Return info for skip handling

        return update_info, None

    def _load_update_config(
        self, app_name: str, update_info: UpdateInfo
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Load app config from UpdateInfo cache or filesystem.

        Args:
            app_name: Name of the app
            update_info: UpdateInfo with cached config

        Returns:
            Tuple of (app_config dict, error message). Config is None on error.

        """
        # Get app config from cached UpdateInfo or load if not available
        if update_info.app_config:
            return update_info.app_config, None

        # Fallback: load if update_info didn't cache it
        try:
            app_config = self._load_app_config_or_fail(
                app_name, "prepare_update"
            )
            return app_config, None
        except ConfigurationError as e:
            logger.error("Config error: %s", e)
            return None, str(e)

    async def _load_catalog_for_update(
        self, app_name: str, app_config: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Load catalog entry if referenced in app config.

        Args:
            app_name: Name of the app
            app_config: App configuration dictionary

        Returns:
            Catalog entry dict or None if not referenced

        Raises:
            UpdateError: If catalog is referenced but not found

        """
        catalog_ref = app_config.get("catalog_ref")
        if not catalog_ref:
            return None

        try:
            return await self._load_catalog_cached(catalog_ref)
        except (FileNotFoundError, ValueError) as e:
            msg = ERROR_CATALOG_MISSING.format(
                app_name=app_name, catalog_ref=catalog_ref
            )
            raise UpdateError(
                message=msg,
                context={"app_name": app_name, "catalog_ref": catalog_ref},
                cause=e,
            ) from e

    def _select_asset_for_update(
        self,
        app_name: str,
        update_info: UpdateInfo,
        catalog_entry: dict[str, Any] | None,
    ) -> tuple[Asset | None, str | None]:
        """Select AppImage asset from release data.

        Args:
            app_name: Name of the app
            update_info: UpdateInfo with release data
            catalog_entry: Optional catalog entry for asset selection

        Returns:
            Tuple of (Asset, error message). Asset is None on error.

        """
        if not update_info.release_data:
            logger.error("No release data available for %s", app_name)
            return None, "No release data available"

        # Convert catalog_entry to dict if needed
        catalog_dict = dict(catalog_entry) if catalog_entry else None
        appimage_asset = select_best_appimage_asset(
            update_info.release_data,
            catalog_entry=catalog_dict,
            installation_source="url",
            raise_on_not_found=False,
        )

        if not appimage_asset:
            logger.error("No AppImage found for %s", app_name)
            return (
                None,
                "AppImage not found in release - may still be building",
            )

        return appimage_asset, None

    async def _prepare_update_context(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        force: bool,
        update_info: UpdateInfo | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Prepare context for update operation.

        Args:
            app_name: Name of the app to update
            session: aiohttp session
            force: Force update even if no new version
            update_info: Optional pre-fetched update info

        Returns:
            Tuple of (context dict, error message). Context is None on error.

        """
        # Resolve update info (cached or fresh check)
        update_info, error = await self._resolve_update_info(
            app_name, session, force, update_info
        )
        if error:
            return None, error
        if not update_info:
            return None, "Failed to resolve update info"

        # Handle skip case (already up to date and not forced)
        if not update_info.has_update and not force:
            return {"skip": True, "success": True}, None

        # Load app configuration
        app_config, error = self._load_update_config(app_name, update_info)
        if error:
            return None, error
        if not app_config:
            return None, "Failed to load app config"

        # Extract GitHub configuration
        github_config = get_github_config(app_config)
        owner = github_config.owner
        repo = github_config.repo

        # Load catalog entry if referenced
        catalog_entry = await self._load_catalog_for_update(
            app_name, app_config
        )

        # Select AppImage asset
        appimage_asset, error = self._select_asset_for_update(
            app_name, update_info, catalog_entry
        )
        if error:
            return None, error

        return {
            "app_config": app_config,
            "update_info": update_info,
            "owner": owner,
            "repo": repo,
            "catalog_entry": catalog_entry,
            "appimage_asset": appimage_asset,
        }, None

    async def update_single_app(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        force: bool = False,
        update_info: UpdateInfo | None = None,
    ) -> tuple[bool, str | None]:
        """Update a single app using direct parameter passing.

        Args:
            app_name: Name of the app to update
            session: aiohttp session
            force: Force update even if no new version available
            update_info: Optional pre-fetched update info with cached release data

        Returns:
            Tuple of (success status, error reason or None)

        Raises:
            UpdateError: If update fails (download, verification, processing)
            VerificationError: If hash verification fails
            ConfigurationError: If app configuration is invalid or missing

        """
        try:
            # Prepare update context
            context, error = await self._prepare_update_context(
                app_name, session, force, update_info
            )
            if error or context is None:
                return False, error
            if context.get("skip"):
                return True, None

            # Extract from context with runtime type checking
            app_config = context["app_config"]
            update_info_raw = context.get("update_info")
            if not isinstance(update_info_raw, UpdateInfo):
                msg = "Invalid update context: missing or invalid UpdateInfo"
                return False, msg
            update_info = update_info_raw
            appimage_asset = context["appimage_asset"]

            # Setup paths
            storage_dir = Path(self.global_config["directory"]["storage"])
            icon_dir = Path(self.global_config["directory"]["icon"])
            download_dir = Path(self.global_config["directory"]["download"])

            # Get download path
            filename = extract_filename_from_url(
                appimage_asset.browser_download_url
            )
            download_path = download_dir / filename

            # Backup current version
            installed_path_str = app_config.get("state", {}).get(
                "installed_path", ""
            )
            current_appimage_path = (
                Path(installed_path_str)
                if installed_path_str
                else storage_dir / f"{app_name}.AppImage"
            )
            if current_appimage_path.exists():
                backup_path = self.backup_service.create_backup(
                    current_appimage_path,
                    app_name,
                    update_info.current_version,
                )
                if backup_path:
                    logger.debug("Backup created: %s", backup_path)

            # Download AppImage
            download_service = DownloadService(session, self.progress_reporter)
            self._initialize_services(session)
            downloaded_path = await download_service.download_appimage(
                appimage_asset, download_path
            )
            if not downloaded_path:
                raise UpdateError(
                    message="Download failed",
                    context={
                        "app_name": app_name,
                        "download_url": appimage_asset.browser_download_url,
                    },
                )

            # release_data is guaranteed to exist at this point
            if update_info.release_data is None:
                raise UpdateError(
                    message="release_data must be available",
                    context={"app_name": app_name},
                )

            # Create processing context
            post_context = PostDownloadContext(
                app_name=app_name,
                downloaded_path=downloaded_path,
                asset=appimage_asset,
                release=update_info.release_data,
                app_config=app_config,
                catalog_entry=context["catalog_entry"],
                operation_type=OperationType.UPDATE,
                owner=context["owner"],
                repo=context["repo"],
                verify_downloads=True,  # Always verify updates
                source="catalog" if context.get("catalog_entry") else "url",
            )

            # Process download
            result = await self.post_download_processor.process(post_context)

            if result.success:
                logger.debug(
                    "✅ Successfully updated %s to %s",
                    app_name,
                    update_info.latest_version,
                )
                return True, None
            return False, result.error or "Post-download processing failed"

        except (UpdateError, VerificationError) as e:
            # Re-raise domain exceptions as they already have context
            logger.exception("Failed to update %s", app_name)
            return False, str(e)
        except Exception as e:
            # Wrap unexpected exceptions in UpdateError with context
            logger.exception("Failed to update %s", app_name)
            raise UpdateError(
                message=f"Update failed: {e}",
                context={
                    "app_name": app_name,
                    "force": force,
                },
                cause=e,
            ) from e

    async def _load_catalog_cached(self, ref: str) -> dict[str, Any] | None:
        """Load catalog with in-memory caching for current session.

        This cache persists for the lifetime of the UpdateManager instance,
        reducing redundant file I/O when multiple apps share the same catalog.
        Uses asyncio.Lock to ensure thread-safe concurrent access.

        Args:
            ref: Catalog reference name (e.g., "qownnotes")

        Returns:
            Catalog entry dict or None if not found

        Raises:
            FileNotFoundError: If catalog file not found
            ValueError: If catalog JSON is invalid or malformed

        Performance:
            - First load: ~1-2ms (file I/O + JSON parse + validation)
            - Cached load: ~0.01ms (dict lookup)
            - Benefit: 100x faster for shared catalogs

        Thread Safety:
            Protected by asyncio.Lock to prevent race conditions during
            concurrent catalog loads.
        """
        async with self._cache_lock:
            if ref not in self._catalog_cache:
                entry = self.config_manager.load_catalog(ref)
                # Cache the result (even if None) to avoid repeated lookup failures
                self._catalog_cache[ref] = entry  # type: ignore[assignment]

            return self._catalog_cache.get(ref)

    def _load_app_config_or_fail(
        self, app_name: str, context: str = ""
    ) -> dict[str, Any]:
        """Load app config with consistent error handling.

        Centralizes config loading logic to eliminate duplication and
        ensure consistent error messages across all call sites.

        Args:
            app_name: Name of app to load config for
            context: Optional context for error message (e.g., "check_update", "prepare_update")

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
            msg = f"{prefix}{ERROR_CONFIGURATION_MISSING.format(app_name=app_name)}"
            raise ConfigurationError(msg)
        return config

    async def _update_cached_progress(self, app_name: str) -> None:
        """Update progress for cached update info.

        Args:
            app_name: Name of the app being processed

        """
        if not self._shared_api_task_id:
            return

        # Null object pattern: no need for None check on progress_reporter
        if not self.progress_reporter.is_active():
            return

        try:
            task_info = self.progress_reporter.get_task_info(
                self._shared_api_task_id
            )
            if not task_info:
                return

            completed = task_info.get("completed", 0)
            total_value = task_info.get("total")
            new_completed = int(completed) + 1
            total = (
                int(total_value)
                if total_value and total_value > 0
                else new_completed
            )
            await self.progress_reporter.update_task(
                self._shared_api_task_id,
                completed=float(new_completed),
                description=f"🌐 Retrieved {app_name} (cached) ({new_completed}/{total})",
            )
        except Exception as e:
            logger.debug(
                "Progress update failed for %s: %s",
                app_name,
                e,
                exc_info=True,
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
            - success status dict: maps app names to True/False
            - error reasons dict: maps failed app names to error messages

        Note:
            This method catches all exceptions per-app to ensure partial
            success. Individual app failures are captured in the error_reasons
            dict rather than propagating exceptions.

        """
        # Set shared API task ID for progress tracking
        # TODO: This will be further refactored when we inject dependencies
        if api_task_id:
            self._shared_api_task_id = api_task_id

        semaphore = asyncio.Semaphore(
            self.global_config["max_concurrent_downloads"]
        )
        results: dict[str, bool] = {}
        error_reasons: dict[str, str] = {}

        # Create lookup map for update infos
        update_info_map: dict[str, UpdateInfo] = {}
        if update_infos:
            update_info_map = {info.app_name: info for info in update_infos}
            logger.debug(
                "Using cached update info for %d apps (eliminates cache re-reads)",
                len(update_info_map),
            )

        async with aiohttp.ClientSession() as session:

            async def update_with_semaphore(
                app_name: str,
            ) -> tuple[str, bool, str | None]:
                cached_info = update_info_map.get(app_name)

                # Update progress for cached data outside semaphore
                if cached_info:
                    await self._update_cached_progress(app_name)

                async with semaphore:
                    success, error_reason = await self.update_single_app(
                        app_name, session, force, cached_info
                    )
                    return app_name, success, error_reason

            tasks = [update_with_semaphore(app) for app in app_names]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in task_results:
                if isinstance(result, tuple):
                    app_name, success, error_reason = result
                    results[app_name] = success
                    if not success and error_reason:
                        error_reasons[app_name] = error_reason
                elif isinstance(result, Exception):
                    logger.error("Update task failed: %s", result)
                    error_reasons[VERSION_UNKNOWN] = f"Task failed: {result}"

        return results, error_reasons
