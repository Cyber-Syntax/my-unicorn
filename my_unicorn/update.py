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

        # Initialize progress service
        from my_unicorn.services.progress import get_progress_service

        self.progress_service = progress_service or get_progress_service()

        # Initialize shared services - will be set when session is available
        self.icon_service = None
        self.verification_service = None

    def _initialize_services(self, session: Any) -> None:
        """Initialize shared services with HTTP session.

        Args:
            session: aiohttp session for downloads

        """
        from .services import IconService, VerificationService

        download_service = DownloadService(session)
        self.icon_service = IconService(download_service)
        self.verification_service = VerificationService(download_service)

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
        self, app_name: str, session: aiohttp.ClientSession
    ) -> UpdateInfo | None:
        """Check for updates for a single app.

        Args:
            app_name: Name of the app to check
            session: aiohttp session

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

            # Fetch latest release
            fetcher = GitHubReleaseFetcher(owner, repo, session)
            if should_use_prerelease:
                logger.debug("Fetching latest prerelease for %s/%s", owner, repo)
                try:
                    release_data = await fetcher.fetch_latest_prerelease()
                except ValueError as e:
                    if "No prereleases found" in str(e):
                        logger.warning(
                            "No prereleases found for %s/%s, falling back to latest release",
                            owner,
                            repo,
                        )
                        release_data = await fetcher.fetch_latest_release()
                    else:
                        raise
            else:
                release_data = await fetcher.fetch_latest_release()

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
        self, app_names: list[str] | None = None
    ) -> list[UpdateInfo]:
        """Check for updates for all or specified apps with progress tracking.

        This method creates progress tasks for each app being checked and updates them
        as the checks complete. Should be called within an active progress session.

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

        # Check if progress session is active for progress tracking
        progress_enabled = self.progress_service.is_active()
        check_tasks = {}  # Map app_name to progress task_id

        # Create progress tasks for each app being checked
        if progress_enabled:
            for app_name in app_names:
                try:
                    task_id = await self.progress_service.create_update_task(app_name)
                    await self.progress_service.update_task(
                        task_id,
                        completed=0.0,
                        description=f"🔍 Checking {app_name} for updates...",
                    )
                    check_tasks[app_name] = task_id
                except Exception:
                    # If progress task creation fails, continue without progress for this app
                    pass

        semaphore = asyncio.Semaphore(self.global_config["max_concurrent_downloads"])

        async with aiohttp.ClientSession() as session:

            async def check_with_semaphore_and_progress(app_name: str) -> UpdateInfo | None:
                async with semaphore:
                    try:
                        # Update progress to show checking is in progress
                        if progress_enabled and app_name in check_tasks:
                            await self.progress_service.update_task(
                                check_tasks[app_name],
                                completed=50.0,
                                description=f"🔍 Checking {app_name}...",
                            )

                        result = await self.check_single_update(app_name, session)

                        # Update progress to show check completed
                        if progress_enabled and app_name in check_tasks:
                            if result and result.has_update:
                                description = f"📦 {app_name} update available"
                            else:
                                description = f"✅ {app_name} is up to date"

                            await self.progress_service.update_task(
                                check_tasks[app_name], completed=100.0, description=description
                            )
                            await self.progress_service.finish_task(check_tasks[app_name])

                        return result
                    except Exception as e:
                        # Handle errors and clean up progress
                        if progress_enabled and app_name in check_tasks:
                            await self.progress_service.update_task(
                                check_tasks[app_name],
                                completed=0.0,
                                description=f"❌ Failed to check {app_name}",
                            )
                            await self.progress_service.finish_task(check_tasks[app_name])
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
        # Create progress task for this update (only if progress session is active)
        update_task_id = None
        progress_enabled = self.progress_service.is_active()

        if progress_enabled:
            try:
                update_task_id = await self.progress_service.create_update_task(app_name)
            except Exception:
                # If progress task creation fails, disable progress for this update
                progress_enabled = False

        try:
            # Phase 1: Initial checks (0-15%)
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id,
                    completed=0.0,
                    description=f"🔍 Checking {app_name} for updates...",
                )

            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                logger.error("No config found for app: %s", app_name)
                if progress_enabled and update_task_id:
                    await self.progress_service.finish_task(update_task_id)
                return False

            # Check for updates first
            update_info = await self.check_single_update(app_name, session)
            if not update_info:
                logger.error("Failed to check updates for %s", app_name)
                if progress_enabled and update_task_id:
                    await self.progress_service.finish_task(update_task_id)
                return False

            if progress_enabled and update_task_id:
                await self.progress_service.update_task(update_task_id, completed=10.0)

            if not force and not update_info.has_update:
                logger.debug("%s is already up to date", app_name)
                if progress_enabled and update_task_id:
                    await self.progress_service.update_task(
                        update_task_id,
                        completed=100.0,
                        description=f"✅ {app_name} is up to date",
                    )
                    await self.progress_service.finish_task(update_task_id)
                return True

            logger.debug(
                f"Updating {app_name} from {update_info.current_version} to {update_info.latest_version}"
            )

            if progress_enabled and update_task_id:
                await self.progress_service.update_task(update_task_id, completed=15.0)

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

            fetcher = GitHubReleaseFetcher(owner, repo, session)
            if should_use_prerelease:
                logger.debug("Fetching latest prerelease for %s/%s", owner, repo)
                release_data = await fetcher.fetch_latest_prerelease()
            else:
                release_data = await fetcher.fetch_latest_release()

            # Find AppImage asset using source-aware selection
            appimage_asset = self._select_best_appimage_by_source(
                fetcher, release_data, app_config
            )

            if not appimage_asset:
                logger.error("No AppImage found for %s", app_name)
                return False

            # Phase 2: Setup and backup (15-30%)
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id,
                    completed=20.0,
                    description=f"⚙️ Preparing {app_name} update...",
                )

            # Set up paths
            storage_dir = self.global_config["directory"]["storage"]
            backup_dir = self.global_config["directory"]["backup"]
            icon_dir = self.global_config["directory"]["icon"]
            download_dir = self.global_config["directory"]["download"]

            # Create backup of current version
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id, completed=25.0, description=f"💾 Backing up {app_name}..."
                )

            current_appimage_path = storage_dir / app_config["appimage"]["name"]
            if current_appimage_path.exists():
                backup_path = self.backup_service.create_backup(
                    current_appimage_path, app_name, update_info.current_version
                )
                if backup_path:
                    logger.debug("💾 Backup created: %s", backup_path)

            if progress_enabled and update_task_id:
                await self.progress_service.update_task(update_task_id, completed=30.0)

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
                        fetcher = GitHubReleaseFetcher(owner, repo, session)
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

            # Phase 3: Download preparation (30-35%)
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id, completed=30.0, description=f"📦 Downloading {app_name}..."
                )

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

            # Phase 4: Post-download processing (35-70%)
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id, completed=35.0, description=f"⚙️ Processing {app_name}..."
                )

            # Get icon using enhanced IconManager with extraction configuration
            icon_path = None
            updated_icon_config = None

            # Check if icon setup should be attempted (with or without initial icon_asset)
            should_setup_icon = (
                bool(icon_asset)
                or app_config.get("icon", {}).get("installed")
                or (catalog_entry and catalog_entry.get("icon"))
            )

            if should_setup_icon:
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
                )

            if progress_enabled and update_task_id:
                await self.progress_service.update_task(update_task_id, completed=50.0)

            # Update progress for verification phase
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id, completed=55.0, description=f"📦 Downloaded {app_name}"
                )

            # Create verification task in post-processing
            verification_task_id = None
            if progress_enabled:
                verification_task_id = await self.progress_service.create_verification_task(
                    appimage_path.name
                )
                await self.progress_service.update_task(
                    verification_task_id,
                    completed=0.0,
                    description=f"🔍 Verifying {app_name}...",
                )

            verification_config = app_config.get("verification", {})
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
                )

                if progress_enabled and verification_task_id:
                    await self.progress_service.update_task(
                        verification_task_id,
                        completed=100.0,
                        description=f"✅ Verified {app_name}",
                    )
                    await self.progress_service.finish_task(verification_task_id, success=True)

            except Exception as e:
                logger.error("Verification failed for %s: %s", app_name, e)
                if progress_enabled and verification_task_id:
                    await self.progress_service.update_task(
                        verification_task_id,
                        completed=0.0,
                        description="❌ Verification failed",
                    )
                    await self.progress_service.finish_task(
                        verification_task_id, success=False
                    )
                # Continue with update even if verification fails
                verification_results = {}
                updated_verification_config = {}

            # Continue with remaining update steps
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id,
                    completed=65.0,
                    description=f"📝 Updating {app_name} config...",
                )

            # Phase 5: Installation (70-90%)
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id, completed=70.0, description=f"📁 Installing {app_name}..."
                )

            # Now make executable and move to install directory
            self.storage_service.make_executable(appimage_path)
            appimage_path = self.storage_service.move_to_install_dir(appimage_path)

            if progress_enabled and update_task_id:
                await self.progress_service.update_task(update_task_id, completed=80.0)

            # Finally rename to clean name using catalog configuration
            if rename_to:
                clean_name = self.storage_service.get_clean_appimage_name(rename_to)
                appimage_path = self.storage_service.rename_appimage(appimage_path, clean_name)

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

            # Update desktop entry to reflect any changes (icon, paths, etc.)
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

            logger.debug(
                "✅ Successfully updated %s to %s", app_name, update_info.latest_version
            )
            if stored_hash:
                logger.debug("🔐 Updated stored hash: %s", stored_hash)

            # Phase 6: Complete (100%)
            if progress_enabled and update_task_id:
                await self.progress_service.update_task(
                    update_task_id,
                    completed=100.0,
                    description=f"✅ {app_name} updated successfully",
                )
                await self.progress_service.finish_task(update_task_id)

            return True

        except Exception as e:
            # Make sure to finish the progress task on error
            if progress_enabled and update_task_id:
                try:
                    await self.progress_service.update_task(
                        update_task_id,
                        completed=0.0,
                        description=f"❌ {app_name} update failed",
                    )
                    await self.progress_service.finish_task(update_task_id)
                except Exception:
                    # If progress update fails, just continue with error logging
                    pass
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
    ) -> tuple[Path | None, dict[str, Any]]:
        """Setup icon during update with extraction configuration management.

        Args:
            app_config: Current app configuration
            catalog_entry: Catalog entry for the app (if available)
            app_name: Application name
            icon_dir: Directory where icons should be saved
            appimage_path: Path to AppImage for icon extraction
            icon_asset: Icon asset with filename and URL
            download_service: Service for downloading icons

        Returns:
            Tuple of (Path to acquired icon or None, updated icon config)

        """
        from .services import IconConfig

        current_icon_config = app_config.get("icon", {}) if app_config else {}

        icon_config = IconConfig(
            extraction_enabled=True,  # Will be determined by service
            icon_url=icon_asset["icon_url"],
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
        if self.verification_service is None:
            raise RuntimeError("Verification service not initialized")

        # Convert GitHubAsset to dict for service compatibility
        asset_dict = {
            "digest": getattr(asset, "digest", None),
            "size": getattr(asset, "size", 0),
        }

        result = await self.verification_service.verify_file(
            file_path=path,
            asset=asset_dict,
            config=verification_config,
            owner=owner,
            repo=repo,
            tag_name=tag_name,
            app_name=app_name,
        )

        return result.methods, result.updated_config

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
