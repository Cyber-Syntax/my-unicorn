"""Update management for installed AppImage applications.

This module handles checking for updates, downloading new versions,
and managing the update process for installed AppImages.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

try:
    from packaging.version import InvalidVersion, Version
except ImportError:
    Version = None
    InvalidVersion = None


from .auth import GitHubAuthManager
from .backup import BackupService
from .config import AppConfig, ConfigManager
from .download import DownloadService, IconAsset
from .github_client import GitHubAsset, GitHubReleaseDetails, GitHubReleaseFetcher
from .logger import get_logger
from .services import IconService, VerificationService
from .storage import StorageService

logger = get_logger(__name__)


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

    def _select_best_appimage_by_source(
        self,
        fetcher: GitHubReleaseFetcher,
        release_data: GitHubReleaseDetails,
        app_config: AppConfig,
    ) -> GitHubAsset | None:
        """Select the most appropriate AppImage asset based on the installation source.

        If the source is `"catalog"`, the function uses a list of preferred filename
        suffixes (defined in the app's catalog configuration under
        `appimage.characteristic_suffix`) to prioritize which AppImage file to select.
        The suffixes are checked in the given order.

        Example:
            Catalog config:
                "characteristic_suffix": ["-x86_64", "-arm64", "-linux"]

            Release assets:
                - "myapp-x86_64.AppImage"
                - "myapp-arm64.AppImage"
                - "myapp-linux.AppImage"

            Selected asset: "myapp-x86_64.AppImage" (first match in order).

        If the source is `"url"` or unknown, suffix preferences are ignored and a
        generic URL-based selection strategy is applied.

        Args:
            fetcher: GitHubReleaseFetcher instance.
            release_data: Release data from the GitHub API.
            app_config: App configuration containing source and suffix preferences.

        Returns:
            The best matching AppImage asset, or None if no suitable file is found.

        """
        source = app_config.get("source", "catalog")

        if source == "catalog":
            # Use suffix preferences from catalog
            characteristic_suffix = app_config["appimage"].get("characteristic_suffix", [])
            return fetcher.select_best_appimage(
                release_data, characteristic_suffix, installation_source="catalog"
            )
        else:
            # Fallback: URL-based selection
            return fetcher.select_best_appimage(release_data, installation_source="url")

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
                    release_data = await fetcher.fetch_latest_prerelease(ignore_cache=refresh_cache)
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
            import aiohttp

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

    async def check_all_updates_with_status_spinner(
        self, app_names: list[str] | None = None
    ) -> list[UpdateInfo]:
        """Check for updates with Rich Status spinner for check-only operations.

        Uses Rich Status spinner which is safe for check-only operations that
        don't have active progress sessions.

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

        # Use Rich Status spinner for check-only operations (no progress session)
        from rich.console import Console
        from rich.status import Status

        console = Console()
        with Status(
            f"Checking {len(app_names)} app(s) for updates...",
            console=console,
            spinner="dots",
        ):
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
                        result = await self.check_single_update(app_name, session, refresh_cache=refresh_cache)
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

    # FIXME: too many branches
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
        progress_enabled = progress_service.is_active()

        try:
            # Phase 1: Initial checks

            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                logger.error("No config found for app: %s", app_name)
                return False

            # Check for updates first
            update_info = await self.check_single_update(app_name, session)
            if not update_info:
                logger.error("Failed to check updates for %s", app_name)
                return False

            if not force and not update_info.has_update:
                logger.debug("%s is already up to date", app_name)
                return True

            logger.debug(
                f"Updating {app_name} from {update_info.current_version} to {update_info.latest_version}"
            )

            # Fetch latest release data
            owner = app_config["owner"]
            repo = app_config["repo"]

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
                return False

            # TODO: DUPLICATE API CALL! This fetches the same release data already fetched in check_single_update()
            # This is why we see 2-3 API calls per app instead of 1
            # Should pass release_data from check phase instead of re-fetching
            fetcher = GitHubReleaseFetcher(owner, repo, session, self._shared_api_task_id)
            if should_use_prerelease:
                logger.debug("Fetching latest prerelease for %s/%s", owner, repo)
                release_data = await fetcher.fetch_latest_prerelease()
            else:
                # Use fallback logic to handle repositories with only prereleases
                release_data = await fetcher.fetch_latest_release_or_prerelease(
                    prefer_prerelease=False
                )

            # Find AppImage asset using source-aware selection
            appimage_asset = self._select_best_appimage_by_source(
                fetcher, release_data, app_config
            )

            if not appimage_asset:
                logger.error("No AppImage found for %s", app_name)
                return False

            # Phase 2: Setup and backup

            # Set up paths
            storage_dir = self.global_config["directory"]["storage"]
            backup_dir = self.global_config["directory"]["backup"]
            icon_dir = self.global_config["directory"]["icon"]
            download_dir = self.global_config["directory"]["download"]

            # Create backup of current version

            current_appimage_path = storage_dir / app_config["appimage"]["name"]
            if current_appimage_path.exists():
                backup_path = self.backup_service.create_backup(
                    current_appimage_path, app_name, update_info.current_version
                )
                if backup_path:
                    logger.debug("💾 Backup created: %s", backup_path)

            # Download and install new version
            icon_asset = None
            icon_url = None
            icon_filename = None

            # Try to get icon info from app config first
            if app_config.get("icon"):
                icon_url = app_config["icon"].get("url")
                icon_filename = app_config["icon"].get("name")

            # If no icon URL in app config, try to get it from catalog
            if not icon_url:
                catalog_entry = self.config_manager.load_catalog_entry(
                    app_config["repo"].lower()
                )
                if catalog_entry and catalog_entry.get("icon"):
                    catalog_icon = catalog_entry.get("icon", {})
                    icon_url = catalog_icon.get("url")
                    if not icon_filename:
                        icon_filename = catalog_icon.get("name")
                    logger.debug(
                        "🎨 Using icon URL from catalog for %s: %s", app_name, icon_url
                    )

            # Process icon URL if we have one
            if icon_url:
                # Check if icon URL is a path template (doesn't start with http)
                if not icon_url.startswith("http"):
                    # Build full URL from path template
                    try:
                        # TODO: This is a 3rd API call for icon URL building
                        # Could be optimized or eliminated if icons are extracted from AppImage
                        fetcher = GitHubReleaseFetcher(
                            owner, repo, session, self._shared_api_task_id
                        )
                        default_branch = await fetcher.get_default_branch()
                        icon_url = fetcher.build_icon_url(icon_url, default_branch)
                        logger.debug(
                            f"🎨 Built icon URL from template during update: {icon_url}"
                        )
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

            # If we still don't have an icon asset but the app should have an icon,
            # create one with a default filename for AppImage extraction to work
            if not icon_asset and app_config.get("icon", {}).get("installed"):
                if not icon_filename:
                    # Generate default icon filename
                    icon_filename = f"{app_name}.png"

                # Create icon asset with empty URL (AppImage extraction only)
                icon_asset = IconAsset(
                    icon_filename=icon_filename,
                    icon_url="",  # Empty URL means AppImage extraction only
                )
                logger.debug(
                    "🎨 Created icon asset for AppImage extraction: %s", icon_filename
                )

            # Initialize services for direct usage
            download_service = DownloadService(session)
            self._initialize_services(session)

            # Get catalog entry early for icon and renaming configuration
            catalog_entry = self.config_manager.load_catalog_entry(app_config["repo"].lower())
            rename_to = app_name  # fallback
            if catalog_entry and catalog_entry.get("appimage", {}).get("rename"):
                rename_to = catalog_entry["appimage"]["rename"]
            else:
                # Fallback to app config for backward compatibility
                rename_to = app_config["appimage"].get("rename", app_name)

            # Phase 3: Download preparation

            # Setup download path
            filename = download_service.get_filename_from_url(
                appimage_asset["browser_download_url"]
            )
            download_path = download_dir / filename

            # Download AppImage first (without renaming)
            # Note: The actual download progress is handled separately by DownloadService
            appimage_path = await download_service.download_appimage(
                appimage_asset, download_path, show_progress=True
            )

            # Phase 4: Post-download processing

            # Create combined post-processing task if progress is enabled
            post_processing_task_id = None
            if (
                progress_enabled
                and hasattr(download_service, "progress_service")
                and download_service.progress_service
                and download_service.progress_service.is_active()
            ):
                post_processing_task_id = (
                    await download_service.progress_service.create_post_processing_task(
                        app_name
                    )
                )

            # Verify download if requested (20% of post-processing)
            verification_results = {}
            updated_verification_config = {}
            
            # Load verification config from catalog if available, otherwise from app config
            verification_config = {}
            if catalog_entry and catalog_entry.get("verification"):
                verification_config = catalog_entry["verification"]
                logger.debug("📋 Using catalog verification config for %s: %s", app_name, verification_config)
            else:
                verification_config = app_config.get("verification", {})
                logger.debug("📋 Using app config verification config for %s: %s", app_name, verification_config)
            
            if post_processing_task_id and progress_enabled:
                await progress_service.update_task(
                    post_processing_task_id,
                    completed=10.0,
                    description=f"🔍 Verifying {app_name}...",
                )

            try:
                (
                    verification_results,
                    updated_verification_config,
                ) = await self._perform_update_verification(
                    appimage_path,
                    appimage_asset,
                    dict(verification_config),  # Cast to dict[str, Any]
                    owner,
                    repo,
                    update_info.original_tag_name,
                    app_name,
                    release_data=release_data,
                    progress_task_id=post_processing_task_id,
                )

                if post_processing_task_id and progress_enabled:
                    await progress_service.update_task(
                        post_processing_task_id,
                        completed=30.0,
                        description=f"✅ {app_name} verification",
                    )

            except Exception as e:
                logger.error("Verification failed for %s: %s", app_name, e)
                # Continue with update even if verification fails
                verification_results = {}
                updated_verification_config = {}

            # Move to install directory and make executable (10% of post-processing)
            if post_processing_task_id and progress_enabled:
                await progress_service.update_task(
                    post_processing_task_id,
                    completed=40.0,
                    description=f"� Moving {app_name} to install directory...",
                )

            self.storage_service.make_executable(appimage_path)
            appimage_path = self.storage_service.move_to_install_dir(appimage_path)

            # Finally rename to clean name using catalog configuration
            if rename_to:
                clean_name = self.storage_service.get_clean_appimage_name(rename_to)
                appimage_path = self.storage_service.rename_appimage(appimage_path, clean_name)

            # Handle icon setup (30% of post-processing)
            icon_path = None
            updated_icon_config = None

            # Check if icon setup should be attempted (with or without initial icon_asset)
            should_setup_icon = (
                bool(icon_asset)
                or app_config.get("icon", {}).get("installed")
                or (catalog_entry and catalog_entry.get("icon"))
            )

            if should_setup_icon:
                if post_processing_task_id and progress_enabled:
                    await progress_service.update_task(
                        post_processing_task_id,
                        completed=50.0,
                        description=f"🎨 Setting up {app_name} icon...",
                    )

                # Create minimal icon_asset if one doesn't exist but icon setup is needed
                if not icon_asset:
                    # Try to get info from catalog or generate defaults
                    icon_filename = None
                    icon_url = ""

                    if catalog_entry and catalog_entry.get("icon"):
                        catalog_icon = catalog_entry.get("icon", {})
                        icon_filename = catalog_icon.get("name")
                        icon_url = catalog_icon.get("url", "")

                    if not icon_filename:
                        icon_filename = f"{app_name}.png"

                    icon_asset = IconAsset(
                        icon_filename=icon_filename,
                        icon_url=icon_url,
                    )
                    logger.debug(
                        f"🎨 Created icon asset from catalog/defaults: {icon_filename}"
                    )

                icon_path, updated_icon_config = await self._setup_update_icon(
                    app_config=app_config,
                    catalog_entry=catalog_entry,
                    app_name=app_name,
                    icon_dir=icon_dir,
                    appimage_path=appimage_path,
                    icon_asset=icon_asset,
                    progress_task_id=post_processing_task_id,
                )

                if post_processing_task_id and progress_enabled:
                    await progress_service.update_task(
                        post_processing_task_id,
                        completed=70.0,
                        description=f"✅ {app_name} icon setup",
                    )

            # Update configuration (20% of post-processing)
            if post_processing_task_id and progress_enabled:
                await progress_service.update_task(
                    post_processing_task_id,
                    completed=80.0,
                    description=f"📁 Creating configuration for {app_name}...",
                )

            # Store the computed hash from verification or GitHub digest
            stored_hash = ""
            if verification_results.get("digest", {}).get("passed"):
                stored_hash = verification_results["digest"]["hash"]
            elif verification_results.get("checksum_file", {}).get("passed"):
                stored_hash = verification_results["checksum_file"]["hash"]
            elif appimage_asset["digest"]:
                stored_hash = appimage_asset["digest"]

            # Update verification config based on what was actually used
            if updated_verification_config:
                if "verification" not in app_config:
                    app_config["verification"] = {}
                app_config["verification"].update(updated_verification_config)
                logger.debug(
                    f"🔧 Updated verification config for {app_name} after successful verification"
                )

            # Update app config
            app_config["appimage"]["version"] = update_info.latest_version
            app_config["appimage"]["name"] = appimage_path.name
            app_config["appimage"]["installed_date"] = datetime.now().isoformat()
            app_config["appimage"]["digest"] = stored_hash

            # Update icon configuration with extraction settings and source tracking
            icon_updated = False
            if updated_icon_config:
                previous_icon_status = app_config.get("icon", {}).get("installed", False)
                if "icon" not in app_config:
                    app_config["icon"] = {}

                # Update icon config with new settings from update process
                app_config["icon"].update(updated_icon_config)
                icon_updated = not previous_icon_status or icon_path is not None

                if icon_path:
                    logger.debug(
                        f"🎨 Icon updated for {app_name}: source={updated_icon_config.get('source', 'unknown')}, "
                        f"extraction={updated_icon_config.get('extraction', False)}"
                    )

            self.config_manager.save_app_config(app_name, app_config)

            # Clean up old backups after successful update
            try:
                self.backup_service.cleanup_old_backups(app_name)
            except Exception as e:
                logger.warning("⚠️  Failed to cleanup old backups for %s: %s", app_name, e)

            # Create desktop entry (10% of post-processing)
            if post_processing_task_id and progress_enabled:
                await progress_service.update_task(
                    post_processing_task_id,
                    completed=90.0,
                    description=f"📁 Creating desktop entry for {app_name}...",
                )

            try:
                try:
                    from .desktop import create_desktop_entry_for_app
                except ImportError:
                    from .desktop import create_desktop_entry_for_app

                desktop_path = create_desktop_entry_for_app(
                    app_name=app_name,
                    appimage_path=appimage_path,
                    icon_path=icon_path,
                    comment=f"{app_name.title()} AppImage Application",
                    categories=["Utility"],
                    config_manager=self.config_manager,
                )
                # Desktop entry creation/update logging is handled by the desktop module
            except Exception as e:
                logger.warning("⚠️  Failed to update desktop entry: %s", e)

            # Finish post-processing task
            if post_processing_task_id and progress_enabled:
                await progress_service.finish_task(
                    post_processing_task_id,
                    success=True,
                    final_description=f"✅ {app_name}",
                )

            logger.debug(
                "✅ Successfully updated %s to %s", app_name, update_info.latest_version
            )
            if stored_hash:
                logger.debug("🔐 Updated stored hash: %s", stored_hash)

            return True

        except Exception as e:
            # Mark post-processing as failed if we have a progress task
            if (
                "post_processing_task_id" in locals()
                and post_processing_task_id
                and progress_enabled
                and hasattr(download_service, "progress_service")
                and download_service.progress_service
            ):
                await progress_service.finish_task(
                    post_processing_task_id,
                    success=False,
                    final_description=f"❌ {app_name} post-processing failed",
                )

            logger.error("Failed to update %s: %s", app_name, e)
            return False

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
