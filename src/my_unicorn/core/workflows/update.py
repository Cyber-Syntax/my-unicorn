"""Update management for installed AppImage applications.

This module handles checking for updates, downloading new versions,
and managing the update process for installed AppImages.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.config.migration.helpers import warn_about_migration
from my_unicorn.config.validation import ConfigurationValidator
from my_unicorn.constants import (
    ERROR_CATALOG_MISSING,
    ERROR_CONFIGURATION_GENERIC,
    ERROR_CONFIGURATION_MISSING,
    ERROR_UNEXPECTED,
    VERSION_UNKNOWN,
)
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.backup import BackupService
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import (
    Asset,
    Release,
    ReleaseFetcher,
    extract_github_config,
)
from my_unicorn.core.verification import VerificationService
from my_unicorn.exceptions import ConfigurationError
from my_unicorn.logger import get_logger
from my_unicorn.ui.display import ProgressDisplay
from my_unicorn.utils.appimage_utils import select_best_appimage_asset
from my_unicorn.utils.download_utils import extract_filename_from_url
from my_unicorn.utils.update_utils import process_post_download
from my_unicorn.utils.version_utils import compare_versions

logger = get_logger(__name__)


@dataclass
class UpdateInfo:
    """Information about an available update.

    This class now includes in-memory caching of release data AND loaded config
    to eliminate redundant cache file reads and config validation during a single
    update operation.
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
    """Manages updates for installed AppImages.

    Thread Safety:
        - Safe for concurrent access across multiple asyncio tasks
        - Catalog cache is protected by asyncio.Lock for concurrent reads/writes
        - Each update operation should use a separate UpdateManager instance
          for isolated progress tracking
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        auth_manager: GitHubAuthManager | None = None,
        progress_service: ProgressDisplay | None = None,
    ) -> None:
        """Initialize update manager.

        Args:
            config_manager: Configuration manager instance
            auth_manager: GitHub authentication manager instance
            progress_service: Optional progress service for tracking updates

        """
        self.config_manager = config_manager or ConfigManager()
        self.global_config = self.config_manager.load_global_config()
        self.auth_manager = auth_manager or GitHubAuthManager.create_default()

        # Initialize storage service with install directory
        storage_dir = self.global_config["directory"]["storage"]
        self.storage_service = FileOperations(storage_dir)

        # Initialize backup service
        self.backup_service = BackupService(
            self.config_manager, self.global_config
        )

        # Store progress service parameter but don't cache global service
        self._progress_service_param = progress_service

        # Initialize shared services - will be set when session is available
        self.verification_service: VerificationService | None = None

        # Shared API progress task ID for consolidated API progress tracking
        self._shared_api_task_id: str | None = None

        # In-memory catalog cache for current update session
        # Cleared when UpdateManager instance is destroyed
        # Thread-safe with asyncio.Lock for concurrent access
        self._catalog_cache: dict[str, dict[str, Any] | None] = {}
        self._cache_lock = asyncio.Lock()

    @classmethod
    def create_default(
        cls,
        config_manager: ConfigManager | None = None,
        progress_service: ProgressDisplay | None = None,
    ) -> "UpdateManager":
        """Create UpdateManager with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            config_manager: Optional configuration manager (creates new if None)
            progress_service: Optional progress service for tracking

        Returns:
            Configured UpdateManager instance

        """
        return cls(
            config_manager=config_manager,
            progress_service=progress_service,
        )

    def _initialize_services(self, session: aiohttp.ClientSession) -> None:
        """Initialize shared services with HTTP session.

        Args:
            session: aiohttp session for downloads

        """
        download_service = DownloadService(
            session, self._progress_service_param
        )
        # Get progress service from download service if available
        progress_service = getattr(download_service, "progress_service", None)
        self.verification_service = VerificationService(
            download_service, progress_service
        )

    async def _load_app_config_for_update(
        self, app_name: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Load and validate app config for update check.

        Args:
            app_name: Name of the app

        Returns:
            Tuple of (app_config, error_message). Config is None on error.

        """
        try:
            config = self._load_app_config_or_fail(app_name, "check_update")
            return config, None
        except ConfigurationError as e:
            logger.warning("Config error: %s", e)
            return None, str(e)

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
        fetcher = ReleaseFetcher(owner, repo, session, self.auth_manager)
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
        source_config = app_config.get("source", {})
        owner = source_config.get("owner", VERSION_UNKNOWN)
        repo = source_config.get("repo", VERSION_UNKNOWN)

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
            UpdateInfo object with error_reason set if check failed

        """
        try:
            # Load app config
            app_config, error_msg = await self._load_app_config_for_update(
                app_name
            )
            if app_config is None:
                return UpdateInfo(
                    app_name=app_name,
                    error_reason=error_msg or ERROR_CONFIGURATION_GENERIC,
                )

            # Extract config values
            current_version = app_config.get("state", {}).get(
                "version", VERSION_UNKNOWN
            )
            source_config = app_config.get("source", {})
            owner = source_config.get("owner", VERSION_UNKNOWN)
            repo = source_config.get("repo", VERSION_UNKNOWN)
            should_use_prerelease = source_config.get("prerelease", False)

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
            return UpdateInfo(
                app_name=app_name,
                error_reason=error_msg,
            )

        except ValueError as e:
            # Handle specific ValueError cases (no releases, parsing errors)
            logger.exception("Failed to check updates for %s", app_name)
            return UpdateInfo(
                app_name=app_name,
                error_reason=str(e),
            )

        except Exception as e:
            # Catch-all for unexpected errors
            logger.exception("Failed to check updates for %s", app_name)
            return UpdateInfo(
                app_name=app_name,
                error_reason=ERROR_UNEXPECTED.format(error=e),
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
            List of UpdateInfo objects

        """
        warn_about_migration(self.config_manager)

        if app_names is None:
            app_names = self.config_manager.list_installed_apps()

        if not app_names:
            logger.info("No installed apps found")
            return []

        logger.info("🔄 Checking %d app(s) for updates...", len(app_names))

        async with aiohttp.ClientSession() as session:

            async def check_single(app_name: str) -> UpdateInfo:
                try:
                    return await self.check_single_update(
                        app_name, session, refresh_cache=refresh_cache
                    )
                except Exception as e:
                    logger.exception("Update check failed for %s", app_name)
                    return UpdateInfo(
                        app_name=app_name,
                        error_reason=f"Exception during check: {e}",
                    )

            tasks = [check_single(app) for app in app_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any unexpected exceptions from gather
        update_infos: list[UpdateInfo] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Update check failed: %s", result)
                update_infos.append(
                    UpdateInfo(
                        app_name=app_names[i],
                        error_reason=f"Critical error: {result}",
                    )
                )
            elif isinstance(result, UpdateInfo):
                update_infos.append(result)

        return update_infos

    async def _validate_update_config(
        self, owner: str, repo: str
    ) -> str | None:
        """Validate GitHub identifiers for security.

        Args:
            owner: GitHub owner
            repo: GitHub repository

        Returns:
            Error message or None if valid

        """
        try:
            # Create a minimal config structure for validation
            config = {"source": {"owner": owner, "repo": repo}}
            ConfigurationValidator.validate_app_config(config)
            return None
        except ValueError as e:
            msg = f"Invalid GitHub configuration: {e}"
            logger.error(msg)
            return msg

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
            ValueError: If catalog reference is invalid

        """
        if not catalog_ref:
            return None

        try:
            return await self._load_catalog_cached(catalog_ref)
        except (FileNotFoundError, ValueError) as e:
            msg = ERROR_CATALOG_MISSING.format(
                app_name=app_name, catalog_ref=catalog_ref
            )
            raise ValueError(msg) from e

    async def _select_update_asset(
        self,
        app_name: str,
        release_data: Release,
        catalog_entry: dict[str, Any] | None,
    ) -> tuple[Asset | None, str | None]:
        """Select best AppImage asset for update.

        Args:
            app_name: Name of the app
            release_data: Release data from GitHub
            catalog_entry: Catalog entry or None

        Returns:
            Tuple of (asset, error message). Asset is None on error.

        """
        catalog_dict = dict(catalog_entry) if catalog_entry else None
        appimage_asset = select_best_appimage_asset(
            release_data,
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

        # Check if update is needed (skip context only if up to date and not forced)
        if not update_info.has_update and not force:
            logger.info("%s is already up to date", app_name)
            return {"skip": True, "success": True}, None

        # Get app config from cached UpdateInfo or load if not available
        # This eliminates redundant validation (was loading 2-3 times before)
        if update_info.app_config:
            app_config = (
                update_info.app_config
            )  # Reuse cached config (no validation!)
        else:
            # Fallback: load if update_info didn't cache it (shouldn't happen in normal flow)
            try:
                app_config = self._load_app_config_or_fail(
                    app_name, "prepare_update"
                )
            except ConfigurationError as e:
                logger.error("Config error: %s", e)
                return None, str(e)

        owner, repo, _ = extract_github_config(app_config)

        # Validate GitHub identifiers for security
        try:
            config = {"source": {"owner": owner, "repo": repo}}
            ConfigurationValidator.validate_app_config(config)
        except ValueError as e:
            msg = f"Invalid GitHub configuration: {e}"
            logger.error(msg)
            return None, msg

        # Load catalog entry if referenced
        catalog_ref = app_config.get("catalog_ref")
        catalog_entry = None
        if catalog_ref:
            try:
                catalog_entry = await self._load_catalog_cached(catalog_ref)
            except (FileNotFoundError, ValueError):
                msg = ERROR_CATALOG_MISSING.format(
                    app_name=app_name, catalog_ref=catalog_ref
                )
                raise ValueError(msg)

        # Find AppImage asset from cached release data
        if not update_info.release_data:
            logger.error("No release data available for %s", app_name)
            return (
                None,
                "No release data available",
            )

        # Convert catalog_entry to dict if needed for select_best_appimage_asset
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
            download_service = DownloadService(
                session, self._progress_service_param
            )
            self._initialize_services(session)
            downloaded_path = await download_service.download_appimage(
                appimage_asset, download_path
            )
            if not downloaded_path:
                return False, "Download failed"

            # Verify, install, and configure
            # release_data is guaranteed to exist at this point
            if update_info.release_data is None:
                msg = "release_data must be available"
                raise ValueError(msg) from None
            success = await process_post_download(
                app_name=app_name,
                app_config=app_config,
                latest_version=update_info.latest_version,
                owner=context["owner"],
                repo=context["repo"],
                catalog_entry=context["catalog_entry"],
                appimage_asset=appimage_asset,
                release_data=update_info.release_data,
                icon_dir=icon_dir,
                storage_dir=storage_dir,
                downloaded_path=downloaded_path,
                verification_service=self.verification_service,  # type: ignore[arg-type]
                storage_service=self.storage_service,
                config_manager=self.config_manager,
                backup_service=self.backup_service,
                progress_service=self._progress_service_param,
            )

            if success:
                logger.debug(
                    "✅ Successfully updated %s to %s",
                    app_name,
                    update_info.latest_version,
                )
                return True, None
            return False, "Post-download processing failed"

        except Exception as e:
            logger.exception("Failed to update %s", app_name)
            return False, f"Update failed: {e}"

    async def _load_catalog_cached(self, ref: str) -> dict[str, Any] | None:
        """Load catalog with in-memory caching for current session.

        This cache persists for the lifetime of the UpdateManager instance,
        reducing redundant file I/O when multiple apps share the same catalog.
        Uses asyncio.Lock to ensure thread-safe concurrent access.

        Args:
            ref: Catalog reference name (e.g., "qownnotes")

        Returns:
            Catalog entry dict or None if not found

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

        progress_service = self._progress_service_param
        if not progress_service or not progress_service.is_active():
            return

        try:
            task_info = progress_service.get_task_info(
                self._shared_api_task_id
            )
            if not task_info:
                return

            new_completed = int(task_info.completed) + 1
            total = (
                int(task_info.total) if task_info.total > 0 else new_completed
            )
            await progress_service.update_task(
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
