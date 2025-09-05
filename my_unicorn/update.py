"""Update management for installed AppImage applications.

This module handles checking for updates, downloading new versions,
and managing the update process for installed AppImages.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

try:
    from packaging.version import InvalidVersion, Version
except ImportError:
    Version = None  # type: ignore
    InvalidVersion = None  # type: ignore


from my_unicorn.services.icon_service import IconService
from my_unicorn.services.verification_service import VerificationService

from .auth import GitHubAuthManager
from .backup import BackupService
from .config import ConfigManager
from .download import DownloadService, IconAsset
from .github_client import GitHubAsset, GitHubReleaseFetcher
from .logger import get_logger
from .storage import StorageService

logger = get_logger(__name__)


@dataclass(slots=True)
class UpdateContext:
    """Context information for update operations."""

    app_name: str
    app_config: Any  # AppConfig type
    update_info: "UpdateInfo"
    owner: str
    repo: str
    should_use_prerelease: bool
    catalog_entry: Any | None  # CatalogEntry type
    session: aiohttp.ClientSession


@dataclass(slots=True)
class AssetContext:
    """Context for assets (AppImage and icon)."""

    appimage_asset: Any  # GitHubAsset type
    icon_asset: Any | None  # IconAsset type
    release_data: Any  # GitHubReleaseDetails type


@dataclass(slots=True)
class PathContext:
    """Context for file paths during update."""

    storage_dir: Path
    backup_dir: Path
    icon_dir: Path
    download_dir: Path
    download_path: Path


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        app_name: str,
        current_version: str,
        latest_version: str,
        has_update: bool,
        release_url: str = "",
        prerelease: bool = False,
        original_tag_name: str = "",
    ):
        """Initialize update information.

        Args:
            app_name: Name of the application
            current_version: Currently installed version
            latest_version: Latest available version
            has_update: Whether an update is available
            release_url: URL to the release
            prerelease: Whether the latest version is a prerelease
            original_tag_name: Original tag name from GitHub (preserves 'v' prefix)

        """
        self.app_name = app_name
        self.current_version = current_version
        self.latest_version = latest_version
        self.has_update = has_update
        self.release_url = release_url
        self.prerelease = prerelease
        self.original_tag_name = original_tag_name or f"v{latest_version}"

    def __repr__(self) -> str:
        """String representation of update info."""
        status = "Available" if self.has_update else "Up to date"
        return f"UpdateInfo({self.app_name}: {self.current_version} -> {self.latest_version}, {status})"


class UpdateManager:
    """Manages updates for installed AppImages."""

    def __init__(self, config_manager: ConfigManager | None = None, progress_service=None):
        """Initialize update manager.

        Args:
            config_manager: Configuration manager instance
            progress_service: Optional progress service for tracking updates

        """
        self.config_manager = config_manager or ConfigManager()
        self.global_config = self.config_manager.load_global_config()
        self.auth_manager = GitHubAuthManager()

        # Initialize storage service with install directory
        storage_dir = self.global_config["directory"]["storage"]
        self.storage_service = StorageService(storage_dir)

        # Initialize backup service
        self.backup_service = BackupService(self.config_manager, self.global_config)

        # Store progress service parameter but don't cache global service
        self._progress_service_param = progress_service

        # Initialize shared services - will be set when session is available
        self.icon_service = None
        self.verification_service = None

        # Shared API progress task ID for consolidated API progress tracking
        self._shared_api_task_id: str | None = None

    def _initialize_services(self, session: Any) -> None:
        """Initialize shared services with HTTP session.

        Args:
            session: aiohttp session for downloads

        """
        download_service = DownloadService(session)
        # Get progress service from download service if available
        progress_service = getattr(download_service, "progress_service", None)
        self.icon_service = IconService(download_service, progress_service)
        self.verification_service = VerificationService(download_service, progress_service)

    def _compare_versions(self, current: str, latest: str) -> bool:
        """Compare version strings to determine if update is available.

        Args:
            current: Current version string
            latest: Latest version string

        Returns:
            True if latest is newer than current

        """
        current_clean = current.lstrip("v").lower()
        latest_clean = latest.lstrip("v").lower()

        if current_clean == latest_clean:
            return False

        # Try using packaging.version for proper semantic version comparison
        if Version is not None:
            try:
                current_version = Version(current_clean)
                latest_version = Version(latest_clean)
                return latest_version > current_version
            except InvalidVersion:
                # Fall through to legacy comparison if parsing fails
                pass

        # Legacy comparison for backward compatibility
        try:
            current_parts = [int(x) for x in current_clean.split(".")]
            latest_parts = [int(x) for x in latest_clean.split(".")]

            # Pad shorter version with zeros
            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))

            return latest_parts > current_parts

        except ValueError:
            # Fallback to string comparison
            return latest_clean > current_clean

    async def check_single_update(
        self, app_name: str, session: aiohttp.ClientSession, refresh_cache: bool = False
    ) -> UpdateInfo | None:
        """Check for updates for a single app.

        Args:
            app_name: Name of the app to check
            session: aiohttp session
            refresh_cache: If True, bypass cache and fetch fresh data from API

        Returns:
            UpdateInfo object or None if app not found

        """
        try:
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                logger.warning("No config found for app: %s", app_name)
                return None

            # DEBUG: Log source immediately after loading from disk
            original_source = app_config.get("source", "NOT_SET")
            logger.debug(f"🔍 DEBUG: Source immediately after loading config from disk: {original_source}")
            logger.debug(f"🔍 DEBUG: Full app_config keys: {list(app_config.keys())}")

            current_version = app_config["appimage"]["version"]
            owner = app_config["owner"]
            repo = app_config["repo"]

            logger.debug("Checking updates for %s (%s/%s)", app_name, owner, repo)

            # Check if app is configured to use GitHub API
            should_use_github = True
            should_use_prerelease = False

            # Check catalog first (preferred)
            catalog_entry = self.config_manager.load_catalog_entry(app_config["repo"].lower())
            if catalog_entry:
                github_config = catalog_entry.get("github", {})
                should_use_github = github_config.get("repo", True)
                should_use_prerelease = github_config.get("prerelease", False)

            # Fallback to app config for backward compatibility
            if should_use_github and not should_use_prerelease:
                # Check new github section first
                app_github_config = app_config.get("github", {})
                should_use_github = app_github_config.get("repo", should_use_github)
                should_use_prerelease = app_github_config.get("prerelease", False)

                # Fallback to old verification section for backward compatibility
                if not should_use_prerelease:
                    verification_config = app_config.get("verification", {})
                    should_use_prerelease = verification_config.get("prerelease", False)

            if not should_use_github:
                logger.error("GitHub API disabled for %s (github.repo: false)", app_name)
                return None

            # TODO: This is making a duplicate API call!
            # The same release data will be fetched again in update_single_app()
            # This causes 2 API calls per app instead of 1
            # Fetch latest release
            fetcher = GitHubReleaseFetcher(owner, repo, session, self._shared_api_task_id)
            if should_use_prerelease:
                logger.debug("Fetching latest prerelease for %s/%s", owner, repo)
                try:
                    release_data = await fetcher.fetch_latest_prerelease(
                        ignore_cache=refresh_cache
                    )
                except ValueError as e:
                    if "No prereleases found" in str(e):
                        logger.warning(
                            "No prereleases found for %s/%s, falling back to latest release",
                            owner,
                            repo,
                        )
                        # Use fallback logic to handle repositories with only prereleases
                        release_data = await fetcher.fetch_latest_release_or_prerelease(
                            prefer_prerelease=False, ignore_cache=refresh_cache
                        )
                    else:
                        raise
            else:
                # Use fallback logic to handle repositories with only prereleases
                release_data = await fetcher.fetch_latest_release_or_prerelease(
                    prefer_prerelease=False, ignore_cache=refresh_cache
                )

            latest_version = release_data["version"]
            has_update = self._compare_versions(current_version, latest_version)

            return UpdateInfo(
                app_name=app_name,
                current_version=current_version,
                latest_version=latest_version,
                has_update=has_update,
                release_url=f"https://github.com/{owner}/{repo}/releases/tag/{latest_version}",
                prerelease=release_data.get("prerelease", False),
                original_tag_name=release_data.get("original_tag_name", f"v{latest_version}"),
            )

        except Exception as e:
            # Improved error handling for GitHub authentication errors

            if (
                isinstance(e, aiohttp.client_exceptions.ClientResponseError)
                and getattr(e, "status", None) == 401
            ):
                # User-facing error message (no traceback)
                logger.error(
                    f"Failed to check updates for {app_name}: Unauthorized (401). "
                    "This usually means your GitHub Personal Access Token (PAT) is invalid. "
                    "Please set a valid token in your environment or configuration."
                )
                # Suppress traceback from console, log only to file
                import traceback

                logger.set_console_level_temporarily("CRITICAL")
                logger.error("Traceback for Unauthorized (401):\n%s", traceback.format_exc())
                logger.set_console_level_temporarily("WARNING")
                return None
            # Other errors: user-facing message
            logger.error("Failed to check updates for %s: %s", app_name, e)
            # Suppress traceback from console, log only to file
            import traceback

            logger.set_console_level_temporarily("CRITICAL")
            logger.error("Traceback:\n%s", traceback.format_exc())
            logger.set_console_level_temporarily("WARNING")
            return None

    async def check_all_updates(self, app_names: list[str] | None = None) -> list[UpdateInfo]:
        """Check for updates for all or specified apps.

        Args:
            app_names: List of app names to check, or None for all installed apps

        Returns:
            List of UpdateInfo objects

        """
        if app_names is None:
            app_names = self.config_manager.list_installed_apps()

        if not app_names:
            logger.info("No installed apps found")
            return []

        semaphore = asyncio.Semaphore(self.global_config["max_concurrent_downloads"])

        async with aiohttp.ClientSession() as session:

            async def check_with_semaphore(app_name: str) -> UpdateInfo | None:
                async with semaphore:
                    return await self.check_single_update(app_name, session)

            tasks = [check_with_semaphore(app) for app in app_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        update_infos = []
        for result in results:
            if isinstance(result, UpdateInfo):
                update_infos.append(result)
            elif isinstance(result, Exception):
                logger.error("Update check failed: %s", result)

        return update_infos

    async def check_all_updates_with_spinner(
        self, app_names: list[str] | None = None
    ) -> list[UpdateInfo]:
        """Check for updates for all or specified apps with simple text message.

        Uses a simple text message to avoid Rich rendering conflicts with
        the main progress session during updates.

        Args:
            app_names: List of app names to check, or None for all installed apps

        Returns:
            List of UpdateInfo objects

        """
        if app_names is None:
            app_names = self.config_manager.list_installed_apps()

        if not app_names:
            logger.info("No installed apps found")
            return []

        # Simple text message to avoid Rich conflicts
        print(f"🔄 Checking {len(app_names)} app(s) for updates...")
        return await self._check_apps_without_spinner(app_names)

    async def _check_apps_without_spinner(self, app_names: list[str]) -> list[UpdateInfo]:
        """Internal method to check apps without any display wrapper."""
        semaphore = asyncio.Semaphore(self.global_config["max_concurrent_downloads"])
        update_infos = []

        async def check_with_semaphore(app_name: str) -> UpdateInfo | None:
            async with semaphore:
                try:
                    async with aiohttp.ClientSession() as session:
                        result = await self.check_single_update(app_name, session)
                    return result
                except Exception as e:
                    logger.error("Update check failed for %s: %s", app_name, e)
                    return None

        # Check all apps concurrently
        tasks = [check_with_semaphore(app) for app in app_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, UpdateInfo):
                update_infos.append(result)
            elif isinstance(result, Exception):
                logger.error("Update check failed: %s", result)

        return update_infos

    async def check_all_updates_with_progress(
        self, app_names: list[str] | None = None, refresh_cache: bool = False
    ) -> list[UpdateInfo]:
        """Check for updates for all or specified apps with progress tracking.

        This method creates progress tasks for each app being checked and updates them
        as the checks complete. Should be called within an active progress session.

        Args:
            app_names: List of app names to check, or None for all installed apps
            refresh_cache: If True, bypass cache and fetch fresh data from API

        Returns:
            List of UpdateInfo objects

        """
        if app_names is None:
            app_names = self.config_manager.list_installed_apps()

        if not app_names:
            logger.info("No installed apps found")
            return []

        # Check updates without creating progress tasks (checking is quick preparation work)

        semaphore = asyncio.Semaphore(self.global_config["max_concurrent_downloads"])

        async with aiohttp.ClientSession() as session:

            async def check_with_semaphore_and_progress(app_name: str) -> UpdateInfo | None:
                async with semaphore:
                    try:
                        result = await self.check_single_update(
                            app_name, session, refresh_cache=refresh_cache
                        )
                        return result
                    except Exception as e:
                        raise e

            tasks = [check_with_semaphore_and_progress(app) for app in app_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        update_infos = []
        for result in results:
            if isinstance(result, UpdateInfo):
                update_infos.append(result)
            elif isinstance(result, Exception):
                logger.error("Update check failed: %s", result)

        return update_infos

    async def update_single_app(
        self, app_name: str, session: aiohttp.ClientSession, force: bool = False
    ) -> bool:
        """Update a single app.

        Args:
            app_name: Name of the app to update
            session: aiohttp session
            force: Force update even if no new version available

        Returns:
            True if update was successful

        """
        # Get current progress service (not cached instance) for individual tasks
        from my_unicorn.services.progress import get_progress_service

        progress_service = self._progress_service_param or get_progress_service()

        try:
            # Phase 1: Prepare update context
            update_context = await self._prepare_update_context(app_name, session, force)
            if not update_context:
                return False
            if update_context == "NO_UPDATE_NEEDED":
                return True

            # Phase 2: Prepare assets
            asset_context = await self._prepare_assets(update_context)
            if not asset_context.appimage_asset:
                logger.error("No AppImage found for %s", app_name)
                return False

            # Phase 3: Prepare paths
            path_context = self._prepare_paths(asset_context)

            # Phase 4: Download and backup
            downloaded_path = await self._download_and_backup(
                update_context, asset_context, path_context
            )
            if not downloaded_path:
                return False

            # Phase 5: Post-download processing
            success = await self._process_post_download(
                update_context, asset_context, path_context, downloaded_path
            )

            if success:
                logger.debug(
                    "✅ Successfully updated %s to %s",
                    app_name,
                    update_context.update_info.latest_version,
                )

            return success

        except Exception as e:
            logger.error("Failed to update %s: %s", app_name, e)
            return False

    async def _prepare_update_context(
        self, app_name: str, session: aiohttp.ClientSession, force: bool = False
    ) -> UpdateContext | None:
        """Prepare the update context with configuration and update info.

        Args:
            app_name: Name of the app to update
            session: aiohttp session
            force: Force update even if no new version available

        Returns:
            UpdateContext object or None if preparation failed

        """
        # Load app configuration
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error("No config found for app: %s", app_name)
            return None

        # DEBUG: Log source immediately after loading for update context
        loaded_source = app_config.get("source", "NOT_SET")
        logger.debug(f"🔍 DEBUG: Source loaded for UpdateContext creation: {loaded_source}")
        logger.debug(f"🔍 DEBUG: App config has url_metadata: {'url_metadata' in app_config}")

        # Check for updates first
        update_info = await self.check_single_update(app_name, session)
        if not update_info:
            logger.error("Failed to check updates for %s", app_name)
            return None

        if not force and not update_info.has_update:
            logger.debug("%s is already up to date", app_name)
            # Return a special context to indicate no update needed but successful
            return "NO_UPDATE_NEEDED"  # type: ignore

        logger.debug(
            f"Updating {app_name} from {update_info.current_version} to {update_info.latest_version}"
        )

        # Get repository info
        owner = app_config["owner"]
        repo = app_config["repo"]

        # Determine GitHub API settings
        should_use_github = True
        should_use_prerelease = False

        # Check catalog first (preferred)
        catalog_entry = self.config_manager.load_catalog_entry(app_config["repo"].lower())
        if catalog_entry:
            github_config = catalog_entry.get("github", {})
            if isinstance(github_config, dict):
                should_use_github = github_config.get("repo", True)
                should_use_prerelease = github_config.get("prerelease", False)

        # Fallback to app config for backward compatibility
        if should_use_github and not should_use_prerelease:
            # Check new github section first
            app_github_config = app_config.get("github", {})
            should_use_github = app_github_config.get("repo", should_use_github)
            should_use_prerelease = app_github_config.get("prerelease", False)

            # Fallback to old verification section for backward compatibility
            if not should_use_prerelease:
                verification_config = app_config.get("verification", {})
                if isinstance(verification_config, dict):
                    should_use_prerelease = verification_config.get("prerelease", False)

        if not should_use_github:
            logger.error("GitHub API disabled for %s (github.repo: false)", app_name)
            return None

        # DEBUG: Log original source at UpdateContext creation
        logger.debug(f"🔍 DEBUG: Creating UpdateContext for {app_name} with original source: {app_config.get('source', 'NOT_SET')}")

        return UpdateContext(
            owner=owner,
            repo=repo,
            app_name=app_name,
            app_config=app_config,
            update_info=update_info,
            should_use_prerelease=should_use_prerelease,
            catalog_entry=catalog_entry,
            session=session,
        )

    async def _prepare_assets(self, update_context: UpdateContext) -> AssetContext:
        """Prepare assets for the update (AppImage and icon).

        Args:
            update_context: Context with app and update information

        Returns:
            AssetContext with prepared assets

        """
        # Fetch latest release data
        # TODO: DUPLICATE API CALL! This fetches the same release data already fetched in check_single_update()
        # This is why we see 2-3 API calls per app instead of 1
        # Should pass release_data from check phase instead of re-fetching
        fetcher = GitHubReleaseFetcher(
            update_context.owner,
            update_context.repo,
            update_context.session,
            self._shared_api_task_id,
        )

        if update_context.should_use_prerelease:
            logger.debug(
                "Fetching latest prerelease for %s/%s",
                update_context.owner,
                update_context.repo,
            )
            release_data = await fetcher.fetch_latest_prerelease()
        else:
            # Use fallback logic to handle repositories with only prereleases
            release_data = await fetcher.fetch_latest_release_or_prerelease(
                prefer_prerelease=False
            )

        # Find AppImage asset using source-aware selection
        # Extract parameters from app_config and call fetcher directly
        source = update_context.app_config.get("source", "catalog")
        if source == "catalog":
            # Use suffix preferences from catalog
            characteristic_suffix = update_context.app_config["appimage"].get(
                "characteristic_suffix", []
            )
            appimage_asset = fetcher.select_best_appimage(
                release_data, characteristic_suffix, installation_source="catalog"
            )
        else:
            # Fallback: URL-based selection
            appimage_asset = fetcher.select_best_appimage(
                release_data, installation_source="url"
            )

        # Prepare icon asset
        icon_asset = await self._prepare_icon_asset(update_context, fetcher)

        return AssetContext(
            appimage_asset=appimage_asset,
            icon_asset=icon_asset,
            release_data=release_data,
        )

    async def _prepare_icon_asset(
        self, update_context: UpdateContext, fetcher: GitHubReleaseFetcher
    ) -> IconAsset | None:
        """Prepare icon asset for the update.

        Args:
            update_context: Context with app information
            fetcher: GitHub release fetcher for building icon URLs

        Returns:
            IconAsset or None if no icon is needed

        """
        icon_url = None
        icon_filename = None
        icon_asset = None  # Initialize to prevent scope errors

        # Try to get icon info from app config first
        if update_context.app_config.get("icon"):
            icon_url = update_context.app_config["icon"].get("url")
            icon_filename = update_context.app_config["icon"].get("name")

        # If no icon URL in app config, try to get it from catalog
        if not icon_url and update_context.catalog_entry:
            catalog_icon = update_context.catalog_entry.get("icon", {})
            if isinstance(catalog_icon, dict):
                icon_url = catalog_icon.get("url")
                if not icon_filename:
                    icon_filename = catalog_icon.get("name")
                logger.debug(
                    "🎨 Using icon URL from catalog for %s: %s",
                    update_context.app_name,
                    icon_url,
                )

        # Process icon URL if we have one
        if icon_url:
            # Check if icon URL is a path template (doesn't start with http)
            if not icon_url.startswith("http"):
                # Build full URL from path template
                try:
                    # TODO: This is a 3rd API call for icon URL building
                    # Could be optimized or eliminated if icons are extracted from AppImage
                    default_branch = await fetcher.get_default_branch()
                    icon_url = fetcher.build_icon_url(icon_url, default_branch)
                    logger.debug(f"🎨 Built icon URL from template during update: {icon_url}")
                except Exception as e:
                    logger.warning(
                        f"⚠️  Failed to build icon URL from template during update: {e}"
                    )
                    # Skip icon download if template building fails
                    icon_url = None

            # Create icon asset if we have both URL and filename
            if icon_url and icon_filename:
                icon_asset = IconAsset(
                    icon_filename=icon_filename,
                    icon_url=icon_url,
                )
                logger.debug("🎨 Created icon asset for update: %s", icon_filename)
                return icon_asset

        # If we still don't have an icon asset but the app should have an icon,
        # create one with a default filename for AppImage extraction to work
        should_extract_icon = update_context.app_config.get("icon", {}).get("installed") or (
            update_context.catalog_entry
            and update_context.catalog_entry.get("icon", {}).get("extraction")
        )

        if not icon_asset and should_extract_icon:
            if not icon_filename:
                # Try to get filename from catalog first
                if update_context.catalog_entry and update_context.catalog_entry.get(
                    "icon", {}
                ).get("name"):
                    icon_filename = update_context.catalog_entry["icon"]["name"]
                else:
                    # Generate default icon filename
                    icon_filename = f"{update_context.app_name}.png"

            # Create icon asset with empty URL (AppImage extraction only)
            icon_asset = IconAsset(
                icon_filename=icon_filename,
                icon_url="",  # Empty URL means AppImage extraction only
            )
            logger.debug("🎨 Created icon asset for AppImage extraction: %s", icon_filename)
            return icon_asset

        return None

    def _prepare_paths(self, asset_context: AssetContext) -> PathContext:
        """Prepare file paths for the update.

        Args:
            asset_context: Context with asset information

        Returns:
            PathContext with all required paths

        """
        # Set up directory paths
        storage_dir = Path(self.global_config["directory"]["storage"])
        backup_dir = Path(self.global_config["directory"]["backup"])
        icon_dir = Path(self.global_config["directory"]["icon"])
        download_dir = Path(self.global_config["directory"]["download"])

        # Setup download path
        from my_unicorn.download import DownloadService

        download_service_temp = DownloadService(None)  # type: ignore
        filename = download_service_temp.get_filename_from_url(
            asset_context.appimage_asset["browser_download_url"]
        )
        download_path = download_dir / filename

        return PathContext(
            storage_dir=storage_dir,
            backup_dir=backup_dir,
            icon_dir=icon_dir,
            download_dir=download_dir,
            download_path=download_path,
        )

    async def _download_and_backup(
        self,
        update_context: UpdateContext,
        asset_context: AssetContext,
        path_context: PathContext,
    ) -> Path | None:
        """Handle backup and download operations.

        Args:
            update_context: Context with app information
            asset_context: Context with asset information
            path_context: Context with path information

        Returns:
            Path to downloaded file or None if failed

        """
        # Create backup of current version
        current_appimage_path = (
            path_context.storage_dir / update_context.app_config["appimage"]["name"]
        )
        if current_appimage_path.exists():
            backup_path = self.backup_service.create_backup(
                current_appimage_path,
                update_context.app_name,
                update_context.update_info.current_version,
            )
            if backup_path:
                logger.debug("💾 Backup created: %s", backup_path)

        # Initialize services for direct usage
        download_service = DownloadService(update_context.session)
        self._initialize_services(update_context.session)

        # Download AppImage
        appimage_path = await download_service.download_appimage(
            asset_context.appimage_asset, path_context.download_path, show_progress=True
        )

        return appimage_path

    async def _process_post_download(
        self,
        update_context: UpdateContext,
        asset_context: AssetContext,
        path_context: PathContext,
        downloaded_path: Path,
    ) -> bool:
        """Process post-download operations: verification, installation, icon setup, configuration.

        Args:
            update_context: Context with app information
            asset_context: Context with asset information
            path_context: Context with path information
            downloaded_path: Path to downloaded AppImage

        Returns:
            True if processing was successful

        """
        from my_unicorn.services.progress import get_progress_service

        progress_service = self._progress_service_param or get_progress_service()
        progress_enabled = progress_service.is_active()

        try:
            # Create combined post-processing task if progress is enabled
            post_processing_task_id = None
            if progress_enabled:
                post_processing_task_id = await progress_service.create_post_processing_task(
                    update_context.app_name
                )

            # Verify download if requested (20% of post-processing)
            (
                verification_results,
                updated_verification_config,
            ) = await self._handle_verification(
                update_context,
                asset_context,
                downloaded_path,
                progress_service,
                post_processing_task_id,
            )

            # Move to install directory and make executable (10% of post-processing)
            if post_processing_task_id and progress_enabled:
                await progress_service.update_task(
                    post_processing_task_id,
                    completed=40.0,
                    description=f"📁 Moving {update_context.app_name} to install directory...",
                )

            self.storage_service.make_executable(downloaded_path)
            appimage_path = self.storage_service.move_to_install_dir(downloaded_path)

            # Finally rename to clean name using catalog configuration
            appimage_path = self._handle_renaming(update_context, appimage_path)

            # Handle icon setup (30% of post-processing)
            icon_path, updated_icon_config = await self._handle_icon_setup(
                update_context,
                asset_context,
                path_context,
                appimage_path,
                progress_service,
                post_processing_task_id,
            )

            # Update configuration (20% of post-processing)
            await self._handle_configuration_update(
                update_context,
                asset_context,
                appimage_path,
                icon_path,
                verification_results,
                updated_verification_config,
                updated_icon_config,
                progress_service,
                post_processing_task_id,
            )

            # Create desktop entry (10% of post-processing)
            await self._handle_desktop_entry(
                update_context,
                appimage_path,
                icon_path,
                progress_service,
                post_processing_task_id,
            )

            # Finish post-processing task
            if post_processing_task_id and progress_enabled:
                await progress_service.finish_task(
                    post_processing_task_id,
                    success=True,
                    final_description=f"✅ {update_context.app_name}",
                )

            # Store the computed hash
            stored_hash = self._get_stored_hash(
                verification_results, asset_context.appimage_asset
            )
            if stored_hash:
                logger.debug("🔐 Updated stored hash: %s", stored_hash)

            return True

        except Exception:
            # Mark post-processing as failed if we have a progress task
            if post_processing_task_id and progress_enabled:
                await progress_service.finish_task(
                    post_processing_task_id,
                    success=False,
                    final_description=f"❌ {update_context.app_name} post-processing failed",
                )
            raise  # Re-raise the exception to be handled by the main method

    async def _handle_verification(
        self,
        update_context: UpdateContext,
        asset_context: AssetContext,
        downloaded_path: Path,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Handle file verification.

        Returns:
            Tuple of (verification_results, updated_verification_config)

        """
        # Load verification config from catalog if available, otherwise from app config
        verification_config: dict[str, Any] = {}
        if update_context.catalog_entry and update_context.catalog_entry.get("verification"):
            verification_config = dict(update_context.catalog_entry["verification"])
            logger.debug(
                "📋 Using catalog verification config for %s: %s",
                update_context.app_name,
                verification_config,
            )
        else:
            verification_config = update_context.app_config.get("verification", {})
            logger.debug(
                "📋 Using app config verification config for %s: %s",
                update_context.app_name,
                verification_config,
            )

        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=10.0,
                description=f"🔍 Verifying {update_context.app_name}...",
            )

        verification_results: dict[str, Any] = {}
        updated_verification_config: dict[str, Any] = {}

        try:
            (
                verification_results,
                updated_verification_config,
            ) = await self._perform_update_verification(
                downloaded_path,
                asset_context.appimage_asset,
                verification_config,
                update_context.owner,
                update_context.repo,
                update_context.update_info.original_tag_name,
                update_context.app_name,
                release_data=dict(asset_context.release_data),  # Convert to dict
                progress_task_id=post_processing_task_id,
            )

            if post_processing_task_id and progress_service.is_active():
                await progress_service.update_task(
                    post_processing_task_id,
                    completed=30.0,
                    description=f"✅ {update_context.app_name} verification",
                )

        except Exception as e:
            logger.error("Verification failed for %s: %s", update_context.app_name, e)
            # Continue with update even if verification fails
            verification_results = {}
            updated_verification_config = {}

        return verification_results, updated_verification_config

    def _handle_renaming(self, update_context: UpdateContext, appimage_path: Path) -> Path:
        """Handle AppImage renaming based on configuration.

        Returns:
            Path to renamed AppImage

        """
        # Get rename configuration
        rename_to = update_context.app_name  # fallback
        if update_context.catalog_entry and update_context.catalog_entry.get(
            "appimage", {}
        ).get("rename"):
            rename_to = update_context.catalog_entry["appimage"]["rename"]
        else:
            # Fallback to app config for backward compatibility
            rename_to = update_context.app_config["appimage"].get(
                "rename", update_context.app_name
            )

        if rename_to:
            clean_name = self.storage_service.get_clean_appimage_name(rename_to)
            appimage_path = self.storage_service.rename_appimage(appimage_path, clean_name)

        return appimage_path

    async def _handle_icon_setup(
        self,
        update_context: UpdateContext,
        asset_context: AssetContext,
        path_context: PathContext,
        appimage_path: Path,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> tuple[Path | None, dict[str, Any] | None]:
        """Handle icon setup operations.

        Returns:
            Tuple of (icon_path, updated_icon_config)

        """
        # Check if icon setup should be attempted (with or without initial icon_asset)
        should_setup_icon = (
            bool(asset_context.icon_asset)
            or update_context.app_config.get("icon", {}).get("installed")
            or (
                update_context.catalog_entry
                and update_context.catalog_entry.get("icon", {}).get("extraction")
            )
        )

        if not should_setup_icon:
            return None, None

        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=50.0,
                description=f"🎨 Setting up {update_context.app_name} icon...",
            )

        # Create minimal icon_asset if one doesn't exist but icon setup is needed
        icon_asset = asset_context.icon_asset
        if not icon_asset:
            # Try to get info from catalog or generate defaults
            icon_filename = None
            icon_url = ""

            if update_context.catalog_entry and update_context.catalog_entry.get("icon"):
                catalog_icon = update_context.catalog_entry.get("icon", {})
                if isinstance(catalog_icon, dict):
                    icon_filename = catalog_icon.get("name")
                    icon_url = catalog_icon.get("url", "")

            if not icon_filename:
                icon_filename = f"{update_context.app_name}.png"

            icon_asset = IconAsset(
                icon_filename=icon_filename,
                icon_url=icon_url,
            )
            logger.debug(f"🎨 Created icon asset from catalog/defaults: {icon_filename}")

        icon_path, updated_icon_config = await self._setup_update_icon(
            app_config=update_context.app_config,
            catalog_entry=update_context.catalog_entry,
            app_name=update_context.app_name,
            icon_dir=path_context.icon_dir,
            appimage_path=appimage_path,
            icon_asset=icon_asset,
            progress_task_id=post_processing_task_id,
        )

        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=70.0,
                description=f"✅ {update_context.app_name} icon setup",
            )

        return icon_path, updated_icon_config

    async def _handle_configuration_update(
        self,
        update_context: UpdateContext,
        asset_context: AssetContext,
        appimage_path: Path,
        icon_path: Path | None,
        verification_results: dict[str, Any],
        updated_verification_config: dict[str, Any],
        updated_icon_config: dict[str, Any] | None,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> None:
        """Handle configuration updates after successful processing."""
        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=80.0,
                description=f"📁 Creating configuration for {update_context.app_name}...",
            )

        # Store the computed hash from verification or GitHub digest
        stored_hash = self._get_stored_hash(verification_results, asset_context.appimage_asset)

        # DEBUG: Track source field throughout update process
        logger.debug(f"🔍 DEBUG: Source before verification config update: {update_context.app_config.get('source', 'NOT_SET')}")
        logger.debug(f"🔍 DEBUG: updated_verification_config contents: {updated_verification_config}")
        logger.debug(f"🔍 DEBUG: Type of updated_verification_config: {type(updated_verification_config)}")
        
        # CRITICAL DEBUG: Check if updated_verification_config contains a source field
        if updated_verification_config and 'source' in updated_verification_config:
            logger.error(f"🚨 BUG FOUND: updated_verification_config contains source field: {updated_verification_config['source']}")
            logger.error(f"🚨 This will overwrite root source! Current source: {update_context.app_config.get('source', 'NOT_SET')}")

        # Update verification config based on what was actually used
        if updated_verification_config:
            if "verification" not in update_context.app_config:
                update_context.app_config["verification"] = {}
            
            # CRITICAL FIX: If the bug is that updated_verification_config contains root-level fields,
            # we need to filter them out before updating the verification section
            filtered_verification_config = {k: v for k, v in updated_verification_config.items() 
                                           if k not in ['source', 'owner', 'repo', 'appimage', 'icon', 'github']}
            
            if filtered_verification_config != updated_verification_config:
                logger.warning(f"🔧 FILTERED out root-level fields from verification config: "
                            f"Original: {updated_verification_config}, Filtered: {filtered_verification_config}")
            
            update_context.app_config["verification"].update(filtered_verification_config)
            logger.debug(
                f"🔧 Updated verification config for {update_context.app_name} "
                f"after successful verification"
            )

        # DEBUG: Track source field after verification update
        logger.debug(f"🔍 DEBUG: Source after verification config update: {update_context.app_config.get('source', 'NOT_SET')}")

        # Update app config
        update_context.app_config["appimage"]["version"] = (
            update_context.update_info.latest_version
        )
        update_context.app_config["appimage"]["name"] = appimage_path.name
        update_context.app_config["appimage"]["installed_date"] = datetime.now().isoformat()
        update_context.app_config["appimage"]["digest"] = stored_hash

        # DEBUG: Track source field after appimage updates
        logger.debug(f"🔍 DEBUG: Source after appimage config update: {update_context.app_config.get('source', 'NOT_SET')}")

        # Update icon configuration with extraction settings and source tracking
        if updated_icon_config:
            logger.debug(f"🔍 DEBUG: updated_icon_config contents: {updated_icon_config}")
            previous_icon_status = update_context.app_config.get("icon", {}).get(
                "installed", False
            )
            if "icon" not in update_context.app_config:
                update_context.app_config["icon"] = {}

            # Update icon config with new settings from update process
            update_context.app_config["icon"].update(updated_icon_config)
            icon_updated = not previous_icon_status or icon_path is not None

            if icon_path:
                logger.debug(
                    f"🎨 Icon updated for {update_context.app_name}: "
                    f"source={updated_icon_config.get('source', 'unknown')}, "
                    f"extraction={updated_icon_config.get('extraction', False)}"
                )

        # DEBUG: Track source field before final save
        logger.debug(f"🔍 DEBUG: Final source before save: {update_context.app_config.get('source', 'NOT_SET')}")

        self.config_manager.save_app_config(update_context.app_name, update_context.app_config)

        # Clean up old backups after successful update
        try:
            self.backup_service.cleanup_old_backups(update_context.app_name)
        except Exception as e:
            logger.warning(
                "⚠️  Failed to cleanup old backups for %s: %s", update_context.app_name, e
            )

    async def _handle_desktop_entry(
        self,
        update_context: UpdateContext,
        appimage_path: Path,
        icon_path: Path | None,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> None:
        """Handle desktop entry creation."""
        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=90.0,
                description=f"📁 Creating desktop entry for {update_context.app_name}...",
            )

        try:
            from .desktop import create_desktop_entry_for_app

            desktop_path = create_desktop_entry_for_app(
                app_name=update_context.app_name,
                appimage_path=appimage_path,
                icon_path=icon_path,
                comment=f"{update_context.app_name.title()} AppImage Application",
                categories=["Utility"],
                config_manager=self.config_manager,
            )
            # Desktop entry creation/update logging is handled by the desktop module
        except Exception as e:
            logger.warning("⚠️  Failed to update desktop entry: %s", e)

    def _get_stored_hash(
        self, verification_results: dict[str, Any], appimage_asset: GitHubAsset
    ) -> str:
        """Get the hash to store from verification results or asset digest."""
        if verification_results.get("digest", {}).get("passed"):
            return verification_results["digest"]["hash"]
        elif verification_results.get("checksum_file", {}).get("passed"):
            return verification_results["checksum_file"]["hash"]
        elif appimage_asset.get("digest"):
            return appimage_asset["digest"]
        return ""

    async def _setup_update_icon(
        self,
        app_config: Any,
        catalog_entry: Any,
        app_name: str,
        icon_dir: Path,
        appimage_path: Path,
        icon_asset: IconAsset,
        progress_task_id: str | None = None,
    ) -> tuple[Path | None, dict[str, Any]]:
        """Setup icon from configuration using shared IconService.

        Args:
            app_config: Application configuration
            catalog_entry: Catalog entry if available
            app_name: Application name for icon filename
            icon_dir: Directory where icons should be saved
            appimage_path: Path to AppImage for icon extraction
            icon_asset: Icon asset with filename and URL
            progress_task_id: Optional combined post-processing task ID

        Returns:
            Tuple of (Path to acquired icon or None, updated icon config)

        """
        from .services import IconConfig

        current_icon_config = app_config.get("icon", {}) if app_config else {}

        icon_config = IconConfig(
            extraction_enabled=True,  # Will be determined by service
            icon_url=icon_asset["icon_url"] if icon_asset["icon_url"] else None,
            icon_filename=icon_asset["icon_filename"],
            preserve_url_on_extraction=True,  # Preserve URL for future updates
        )

        if self.icon_service is None:
            raise RuntimeError("Icon service not initialized")

        result = await self.icon_service.acquire_icon(
            icon_config=icon_config,
            app_name=app_name,
            icon_dir=icon_dir,
            appimage_path=appimage_path,
            current_config=current_icon_config,
            catalog_entry=catalog_entry,
            progress_task_id=progress_task_id,
        )

        return result.icon_path, result.config

    async def _perform_update_verification(
        self,
        path: Path,
        asset: GitHubAsset,
        verification_config: dict[str, Any],
        owner: str,
        repo: str,
        tag_name: str,
        app_name: str,
        release_data: dict[str, Any] | None = None,
        progress_task_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Perform update verification using priority-based approach.

        Args:
            path: Path to downloaded file
            asset: GitHub asset information
            verification_config: Current verification configuration
            owner: Repository owner
            repo: Repository name
            tag_name: Release tag name
            download_service: Download service instance
            app_name: Application name

        Returns:
            Tuple of (verification_results, updated_verification_config)

        """
        logger.debug("🔍 _perform_update_verification called for %s", app_name)
        logger.debug("   📋 Verification config: %s", verification_config)
        logger.debug("   📦 Asset digest: %s", asset.get("digest", "None"))

        if self.verification_service is None:
            raise RuntimeError("Verification service not initialized")

        logger.debug("🔄 About to call VerificationService.verify_file()")

        # Convert GitHubAsset to dict for service compatibility
        asset_dict = {
            "digest": asset.get("digest", ""),
            "size": asset.get("size", 0),
        }

        # Extract assets list from release_data if available
        assets_list = []
        if release_data and "assets" in release_data:
            assets_list = release_data["assets"]

        try:
            logger.debug("🔍 Calling VerificationService.verify_file() with:")
            logger.debug("   - asset_dict: %s", asset_dict)
            logger.debug("   - config: %s", verification_config)
            logger.debug("   - assets_list: %d items", len(assets_list))

            result = await self.verification_service.verify_file(
                file_path=path,
                asset=asset_dict,
                config=verification_config,
                owner=owner,
                repo=repo,
                tag_name=tag_name,
                app_name=app_name,
                assets=assets_list,
                progress_task_id=progress_task_id,
            )

            logger.debug("✅ VerificationService.verify_file() completed successfully")
            logger.debug("   - result.passed: %s", result.passed)
            logger.debug("   - result.methods: %s", list(result.methods.keys()))

            return result.methods, result.updated_config

        except Exception as e:
            logger.error("❌ VerificationService.verify_file() failed: %s", e)
            logger.error("   - Exception type: %s", type(e).__name__)
            import traceback

            logger.debug("   - Traceback: %s", traceback.format_exc())
            raise

    async def update_multiple_apps(
        self, app_names: list[str], force: bool = False
    ) -> dict[str, bool]:
        """Update multiple apps.

        Args:
            app_names: List of app names to update
            force: Force update even if no new version available

        Returns:
            Dictionary mapping app names to success status

        """
        semaphore = asyncio.Semaphore(self.global_config["max_concurrent_downloads"])
        results = {}

        async with aiohttp.ClientSession() as session:

            async def update_with_semaphore(app_name: str) -> tuple[str, bool]:
                async with semaphore:
                    success = await self.update_single_app(app_name, session, force)
                    return app_name, success

            tasks = [update_with_semaphore(app) for app in app_names]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in task_results:
                if isinstance(result, tuple):
                    app_name, success = result
                    results[app_name] = success
                elif isinstance(result, Exception):
                    logger.error("Update task failed: %s", result)

        return results
