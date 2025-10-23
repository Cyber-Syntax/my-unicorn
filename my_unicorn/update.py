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
    Version = None  # type: ignore
    InvalidVersion = None  # type: ignore


from my_unicorn.icon import IconHandler
from my_unicorn.verification import VerificationService

from .auth import GitHubAuthManager
from .backup import BackupService
from .config import ConfigManager
from .download import DownloadService, IconAsset
from .file_ops import FileOperations
from .github_client import Asset, AssetSelector, Release, ReleaseFetcher
from .logger import get_logger

logger = get_logger(__name__)


class UpdateInfo:
    """Information about an available update.

    This class now includes in-memory caching of release data to eliminate
    redundant cache file reads during a single update operation.
    """

    def __init__(
        self,
        app_name: str,
        current_version: str,
        latest_version: str,
        has_update: bool,
        release_url: str = "",
        prerelease: bool = False,
        original_tag_name: str = "",
        release_data: Release | None = None,
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
            release_data: Full release data from GitHub API (in-memory cache)

        """
        self.app_name = app_name
        self.current_version = current_version
        self.latest_version = latest_version
        self.has_update = has_update
        self.release_url = release_url
        self.prerelease = prerelease
        self.original_tag_name = original_tag_name or f"v{latest_version}"
        self.release_data = (
            release_data  # In-memory cache for single operation
        )

    def __repr__(self) -> str:
        """String representation of update info."""
        status = "Available" if self.has_update else "Up to date"
        return f"UpdateInfo({self.app_name}: {self.current_version} -> {self.latest_version}, {status})"


class UpdateManager:
    """Manages updates for installed AppImages."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        progress_service=None,
    ):
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
        self.storage_service = FileOperations(storage_dir)

        # Initialize backup service
        self.backup_service = BackupService(
            self.config_manager, self.global_config
        )

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
        self.icon_service = IconHandler(download_service, progress_service)
        self.verification_service = VerificationService(
            download_service, progress_service
        )

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
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        refresh_cache: bool = False,
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
            logger.debug(
                f"🔍 DEBUG: Source immediately after loading config from disk: {original_source}"
            )
            logger.debug(
                f"🔍 DEBUG: Full app_config keys: {list(app_config.keys())}"
            )

            current_version = app_config["appimage"]["version"]
            owner = app_config["owner"]
            repo = app_config["repo"]

            logger.debug(
                "Checking updates for %s (%s/%s)", app_name, owner, repo
            )

            # Check if app is configured to use GitHub API
            should_use_github = True
            should_use_prerelease = False

            # Check catalog first (preferred)
            catalog_entry = self.config_manager.load_catalog_entry(
                app_config["repo"].lower()
            )
            if catalog_entry:
                github_config = catalog_entry.get("github", {})
                should_use_github = github_config.get("repo", True)
                should_use_prerelease = github_config.get("prerelease", False)

            # Fallback to app config for backward compatibility
            if should_use_github and not should_use_prerelease:
                # Check new github section first
                app_github_config = app_config.get("github", {})
                should_use_github = app_github_config.get(
                    "repo", should_use_github
                )
                should_use_prerelease = app_github_config.get(
                    "prerelease", False
                )

                # Fallback to old verification section for backward compatibility
                if not should_use_prerelease:
                    verification_config = app_config.get("verification", {})
                    should_use_prerelease = verification_config.get(
                        "prerelease", False
                    )

            if not should_use_github:
                logger.error(
                    "GitHub API disabled for %s (github.repo: false)", app_name
                )
                return None

            # TODO: This is making a duplicate API call!
            # The same release data will be fetched again in update_single_app()
            # This causes 2 API calls per app instead of 1
            # Fetch latest release
            fetcher = ReleaseFetcher(
                owner, repo, session, self._shared_api_task_id
            )
            if should_use_prerelease:
                logger.debug(
                    "Fetching latest prerelease for %s/%s", owner, repo
                )
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
                        release_data = (
                            await fetcher.fetch_latest_release_or_prerelease(
                                prefer_prerelease=False,
                                ignore_cache=refresh_cache,
                            )
                        )
                    else:
                        raise
            else:
                # Use fallback logic to handle repositories with only prereleases
                release_data = (
                    await fetcher.fetch_latest_release_or_prerelease(
                        prefer_prerelease=False, ignore_cache=refresh_cache
                    )
                )

            latest_version = release_data.version
            has_update = self._compare_versions(
                current_version, latest_version
            )

            # Cache release data in UpdateInfo for in-memory reuse within single operation
            # This eliminates redundant cache file reads in subsequent update phases
            return UpdateInfo(
                app_name=app_name,
                current_version=current_version,
                latest_version=latest_version,
                has_update=has_update,
                release_url=f"https://github.com/{owner}/{repo}/releases/tag/{latest_version}",
                prerelease=release_data.prerelease,
                original_tag_name=release_data.original_tag_name
                or f"v{latest_version}",
                release_data=release_data,  # Store for in-memory reuse
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
                logger.error(
                    "Traceback for Unauthorized (401):\n%s",
                    traceback.format_exc(),
                )
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

    async def check_updates(
        self,
        app_names: list[str] | None = None,
        show_progress: bool = False,
        refresh_cache: bool = False,
    ) -> list[UpdateInfo]:
        """Check for updates for all or specified apps.

        Args:
            app_names: List of app names to check, or None for all installed
                apps
            show_progress: If True, display progress message
            refresh_cache: If True, bypass cache and fetch fresh data from
                API

        Returns:
            List of UpdateInfo objects

        """
        if app_names is None:
            app_names = self.config_manager.list_installed_apps()

        if not app_names:
            logger.info("No installed apps found")
            return []

        # Show progress message if requested
        if show_progress:
            print(f"🔄 Checking {len(app_names)} app(s) for updates...")

        semaphore = asyncio.Semaphore(
            self.global_config["max_concurrent_downloads"]
        )

        async with aiohttp.ClientSession() as session:

            async def check_with_semaphore(app_name: str) -> UpdateInfo | None:
                async with semaphore:
                    try:
                        return await self.check_single_update(
                            app_name, session, refresh_cache=refresh_cache
                        )
                    except Exception as e:
                        logger.error(
                            "Update check failed for %s: %s", app_name, e
                        )
                        return None

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

    async def update_single_app(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        force: bool = False,
        update_info: UpdateInfo | None = None,
    ) -> bool:
        """Update a single app using direct parameter passing.

        Args:
            app_name: Name of the app to update
            session: aiohttp session
            force: Force update even if no new version available
            update_info: Optional pre-fetched update info with cached release data

        Returns:
            True if update was successful

        """
        try:
            # Load app configuration
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                logger.error("No config found for app: %s", app_name)
                return False

            # Use cached update info if provided, otherwise check for updates
            if not update_info:
                update_info = await self.check_single_update(app_name, session)
                if not update_info:
                    return False

            # Check if update is needed
            if not update_info.has_update and not force:
                logger.info("%s is already up to date", app_name)
                return True

            # Get GitHub configuration
            (
                owner,
                repo,
                catalog_entry,
                use_prerelease,
            ) = await self._get_github_info(app_name, app_config)

            # Find AppImage asset from cached release data
            appimage_asset = self._find_appimage_asset(
                update_info.release_data, catalog_entry
            )
            if not appimage_asset:
                logger.error("No AppImage found for %s", app_name)
                return False

            # Setup paths
            storage_dir = Path(self.global_config["directory"]["storage"])
            backup_dir = Path(self.global_config["directory"]["backup"])
            icon_dir = Path(self.global_config["directory"]["icon"])
            download_dir = Path(self.global_config["directory"]["download"])

            # Get download path
            from my_unicorn.download import DownloadService

            download_service_temp = DownloadService(None)  # type: ignore[arg-type]
            filename = download_service_temp.get_filename_from_url(
                appimage_asset.browser_download_url
            )
            download_path = download_dir / filename

            # Backup current version
            current_appimage_path = (
                storage_dir / app_config["appimage"]["name"]
            )
            if current_appimage_path.exists():
                backup_path = self.backup_service.create_backup(
                    current_appimage_path,
                    app_name,
                    update_info.current_version,
                )
                if backup_path:
                    logger.debug("💾 Backup created: %s", backup_path)

            # Download AppImage
            download_service = DownloadService(session)
            self._initialize_services(session)
            downloaded_path = await download_service.download_appimage(
                appimage_asset, download_path, show_progress=True
            )
            if not downloaded_path:
                return False

            # Verify, install, and configure
            success = await self._process_post_download(
                app_name=app_name,
                app_config=app_config,
                update_info=update_info,
                owner=owner,
                repo=repo,
                catalog_entry=catalog_entry,
                appimage_asset=appimage_asset,
                release_data=update_info.release_data,
                icon_dir=icon_dir,
                storage_dir=storage_dir,
                downloaded_path=downloaded_path,
            )

            if success:
                logger.debug(
                    "✅ Successfully updated %s to %s",
                    app_name,
                    update_info.latest_version,
                )

            return success

        except Exception as e:
            logger.error("Failed to update %s: %s", app_name, e)
            return False

    async def _get_github_info(
        self, app_name: str, app_config: dict[str, Any]
    ) -> tuple[str, str, dict[str, Any] | None, bool]:
        """Get GitHub repository information and settings.

        Args:
            app_name: Name of the app
            app_config: App configuration dictionary

        Returns:
            Tuple of (owner, repo, catalog_entry, use_prerelease)

        """
        owner = app_config["owner"]
        repo = app_config["repo"]

        # Determine GitHub API settings
        should_use_prerelease = False

        # Check catalog first (preferred)
        catalog_entry = self.config_manager.load_catalog_entry(repo.lower())
        if catalog_entry:
            github_config = catalog_entry.get("github", {})
            if isinstance(github_config, dict):
                should_use_prerelease = github_config.get("prerelease", False)

        # Fallback to app config for backward compatibility
        if not should_use_prerelease:
            app_github_config = app_config.get("github", {})
            should_use_prerelease = app_github_config.get("prerelease", False)

            # Fallback to old verification section
            if not should_use_prerelease:
                verification_config = app_config.get("verification", {})
                if isinstance(verification_config, dict):
                    should_use_prerelease = verification_config.get(
                        "prerelease", False
                    )

        return owner, repo, catalog_entry, should_use_prerelease

    def _find_appimage_asset(
        self,
        release_data: Release,
        catalog_entry: dict[str, Any] | None = None,
    ) -> Asset | None:
        """Find best AppImage asset from release data using selection logic.

        For updates, we always prefer stable versions over experimental/beta
        builds to ensure consistency with initial catalog installations.

        Args:
            release_data: Release object from GitHub API
            catalog_entry: Optional catalog entry for preferred suffixes

        Returns:
            Best AppImage Asset object or None if not found

        """
        if not release_data or not release_data.assets:
            return None

        # Get preferred suffixes from catalog if available
        preferred_suffixes = None
        if catalog_entry and catalog_entry.get("appimage"):
            appimage_config = catalog_entry["appimage"]
            if isinstance(appimage_config, dict):
                preferred_suffixes = appimage_config.get("preferred_suffixes")

        # Use "url" installation source to filter out experimental versions
        # This ensures we get stable builds during updates, even for catalog apps
        best_asset = AssetSelector.select_appimage_for_platform(
            release_data,
            preferred_suffixes=preferred_suffixes,
            installation_source="url",  # Filter experimental versions
        )

        return best_asset

    async def _process_post_download(
        self,
        app_name: str,
        app_config: dict[str, Any],
        update_info: UpdateInfo,
        owner: str,
        repo: str,
        catalog_entry: dict[str, Any] | None,
        appimage_asset: Asset,
        release_data: Release,
        icon_dir: Path,
        storage_dir: Path,
        downloaded_path: Path,
    ) -> bool:
        """Process post-download operations.

        Args:
            app_name: Name of the app
            app_config: App configuration
            update_info: Update information
            owner: GitHub owner
            repo: GitHub repository
            catalog_entry: Catalog entry or None
            appimage_asset: AppImage Asset object
            release_data: Release data
            icon_dir: Icon directory path
            storage_dir: Storage directory path
            downloaded_path: Path to downloaded AppImage

        Returns:
            True if processing was successful

        """
        from my_unicorn.progress import get_progress_service

        progress_service = (
            self._progress_service_param or get_progress_service()
        )
        progress_enabled = progress_service.is_active()

        try:
            # Create combined post-processing task if progress is enabled
            post_processing_task_id = None
            if progress_enabled:
                post_processing_task_id = (
                    await progress_service.create_post_processing_task(
                        app_name
                    )
                )

            # Verify download if requested (20% of post-processing)
            (
                verification_results,
                updated_verification_config,
            ) = await self._handle_verification(
                app_name,
                app_config,
                catalog_entry,
                owner,
                repo,
                update_info,
                appimage_asset,
                release_data,
                downloaded_path,
                progress_service,
                post_processing_task_id,
            )

            # Move to install directory and make executable (10%)
            if post_processing_task_id and progress_enabled:
                await progress_service.update_task(
                    post_processing_task_id,
                    completed=40.0,
                    description=f"📁 Moving {app_name} to install directory...",
                )

            self.storage_service.make_executable(downloaded_path)
            appimage_path = self.storage_service.move_to_install_dir(
                downloaded_path
            )

            # Rename to clean name using catalog configuration
            appimage_path = self._handle_renaming(
                app_name, app_config, catalog_entry, appimage_path
            )

            # Handle icon setup (30% of post-processing)
            icon_path, updated_icon_config = await self._handle_icon_setup(
                app_name,
                app_config,
                catalog_entry,
                appimage_asset,
                release_data,
                icon_dir,
                appimage_path,
                progress_service,
                post_processing_task_id,
            )

            # Update configuration (20% of post-processing)
            await self._handle_configuration_update(
                app_name,
                app_config,
                update_info,
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
                app_name,
                app_config,
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
                    final_description=f"✅ {app_name}",
                )

            # Store the computed hash
            stored_hash = self._get_stored_hash(
                verification_results, appimage_asset
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
                    final_description=f"❌ {app_name} post-processing failed",
                )
            raise  # Re-raise the exception to be handled by the main method

    async def _handle_verification(
        self,
        app_name: str,
        app_config: dict[str, Any],
        catalog_entry: dict[str, Any] | None,
        owner: str,
        repo: str,
        update_info: UpdateInfo,
        appimage_asset: Asset,
        release_data: Release,
        downloaded_path: Path,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Handle file verification.

        Args:
            app_name: Name of the app
            app_config: App configuration
            catalog_entry: Catalog entry or None
            owner: GitHub owner
            repo: GitHub repository
            update_info: Update information
            appimage_asset: AppImage Asset object
            release_data: Release data
            downloaded_path: Path to downloaded file
            progress_service: Progress service
            post_processing_task_id: Progress task ID or None

        Returns:
            Tuple of (verification_results, updated_verification_config)

        """
        # Load verification config from catalog or app config
        verification_config: dict[str, Any] = {}
        if catalog_entry and catalog_entry.get("verification"):
            verification_config = dict(catalog_entry["verification"])
            logger.debug(
                "📋 Using catalog verification config for %s: %s",
                app_name,
                verification_config,
            )
        else:
            verification_config = app_config.get("verification", {})
            logger.debug(
                "📋 Using app config verification config for %s: %s",
                app_name,
                verification_config,
            )

        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=10.0,
                description=f"🔍 Verifying {app_name}...",
            )

        verification_results: dict[str, Any] = {}
        updated_verification_config: dict[str, Any] = {}

        try:
            (
                verification_results,
                updated_verification_config,
            ) = await self._perform_update_verification(
                downloaded_path,
                appimage_asset,
                verification_config,
                owner,
                repo,
                update_info.original_tag_name,
                app_name,
                release_data=release_data,
                progress_task_id=post_processing_task_id,
            )

            if post_processing_task_id and progress_service.is_active():
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

        return verification_results, updated_verification_config

    def _handle_renaming(
        self,
        app_name: str,
        app_config: dict[str, Any],
        catalog_entry: dict[str, Any] | None,
        appimage_path: Path,
    ) -> Path:
        """Handle AppImage renaming based on configuration.

        Args:
            app_name: Name of the app
            app_config: App configuration
            catalog_entry: Catalog entry or None
            appimage_path: Path to AppImage

        Returns:
            Path to renamed AppImage

        """
        # Get rename configuration
        rename_to = app_name  # fallback
        if catalog_entry and catalog_entry.get("appimage", {}).get("rename"):
            rename_to = catalog_entry["appimage"]["rename"]
        else:
            # Fallback to app config for backward compatibility
            rename_to = app_config["appimage"].get("rename", app_name)

        if rename_to:
            clean_name = self.storage_service.get_clean_appimage_name(
                rename_to
            )
            appimage_path = self.storage_service.rename_appimage(
                appimage_path, clean_name
            )

        return appimage_path

    async def _handle_icon_setup(
        self,
        app_name: str,
        app_config: dict[str, Any],
        catalog_entry: dict[str, Any] | None,
        appimage_asset: Asset,
        release_data: Release,
        icon_dir: Path,
        appimage_path: Path,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> tuple[Path | None, dict[str, Any] | None]:
        """Handle icon setup operations.

        Args:
            app_name: Name of the app
            app_config: App configuration
            catalog_entry: Catalog entry or None
            appimage_asset: AppImage Asset object
            release_data: Release data
            icon_dir: Icon directory path
            appimage_path: Path to AppImage
            progress_service: Progress service
            post_processing_task_id: Progress task ID or None

        Returns:
            Tuple of (icon_path, updated_icon_config)

        """
        # Check if icon setup should be attempted
        should_setup_icon = app_config.get("icon", {}).get("installed") or (
            catalog_entry and catalog_entry.get("icon", {}).get("extraction")
        )

        if not should_setup_icon:
            return None, None

        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=50.0,
                description=f"🎨 Setting up {app_name} icon...",
            )

        # Try to get info from catalog or generate defaults
        icon_filename = None
        icon_url = ""

        if catalog_entry and catalog_entry.get("icon"):
            catalog_icon = catalog_entry.get("icon", {})
            if isinstance(catalog_icon, dict):
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

        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=70.0,
                description=f"✅ {app_name} icon setup",
            )

        return icon_path, updated_icon_config

    async def _handle_configuration_update(
        self,
        app_name: str,
        app_config: dict[str, Any],
        update_info: UpdateInfo,
        appimage_path: Path,
        icon_path: Path | None,
        verification_results: dict[str, Any],
        updated_verification_config: dict[str, Any],
        updated_icon_config: dict[str, Any] | None,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> None:
        """Handle configuration updates after successful processing.

        Args:
            app_name: Name of the app
            app_config: App configuration
            update_info: Update information
            appimage_path: Path to installed AppImage
            icon_path: Path to icon or None
            verification_results: Verification results
            updated_verification_config: Updated verification config
            updated_icon_config: Updated icon config or None
            progress_service: Progress service
            post_processing_task_id: Progress task ID or None

        """
        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=80.0,
                description=f"📁 Creating configuration for {app_name}...",
            )

        # Store computed hash (will be empty dict if no asset provided)
        stored_hash = ""
        if verification_results.get("digest", {}).get("passed"):
            stored_hash = verification_results["digest"]["hash"]
        elif verification_results.get("checksum_file", {}).get("passed"):
            stored_hash = verification_results["checksum_file"]["hash"]

        # Update verification config based on what was actually used
        if updated_verification_config:
            if "verification" not in app_config:
                app_config["verification"] = {}

            # Filter out root-level fields from verification section
            filtered_verification_config = {
                k: v
                for k, v in updated_verification_config.items()
                if k
                not in [
                    "source",
                    "owner",
                    "repo",
                    "appimage",
                    "icon",
                    "github",
                ]
            }

            if filtered_verification_config != updated_verification_config:
                logger.warning(
                    "🔧 FILTERED out root-level fields: "
                    "Original: %s, Filtered: %s",
                    updated_verification_config,
                    filtered_verification_config,
                )

            app_config["verification"].update(filtered_verification_config)
            logger.debug("🔧 Updated verification config for %s", app_name)

        # Update app config
        app_config["appimage"]["version"] = update_info.latest_version
        app_config["appimage"]["name"] = appimage_path.name
        app_config["appimage"]["installed_date"] = datetime.now().isoformat()
        app_config["appimage"]["digest"] = stored_hash

        # Update icon configuration
        if updated_icon_config:
            previous_icon_status = app_config.get("icon", {}).get(
                "installed", False
            )
            if "icon" not in app_config:
                app_config["icon"] = {}

            # Update icon config with new settings from update process
            app_config["icon"].update(updated_icon_config)

            if icon_path:
                logger.debug(
                    "🎨 Icon updated for %s: source=%s, extraction=%s",
                    app_name,
                    updated_icon_config.get("source", "unknown"),
                    updated_icon_config.get("extraction", False),
                )

        self.config_manager.save_app_config(app_name, app_config)

        # Clean up old backups after successful update
        try:
            self.backup_service.cleanup_old_backups(app_name)
        except Exception as e:
            logger.warning(
                "⚠️  Failed to cleanup old backups for %s: %s",
                app_name,
                e,
            )

    async def _handle_desktop_entry(
        self,
        app_name: str,
        app_config: dict[str, Any],
        appimage_path: Path,
        icon_path: Path | None,
        progress_service: Any,
        post_processing_task_id: str | None,
    ) -> None:
        """Handle desktop entry creation.

        Args:
            app_name: Name of the app
            app_config: App configuration
            appimage_path: Path to installed AppImage
            icon_path: Path to icon or None
            progress_service: Progress service
            post_processing_task_id: Progress task ID or None

        """
        if post_processing_task_id and progress_service.is_active():
            await progress_service.update_task(
                post_processing_task_id,
                completed=90.0,
                description=f"📁 Creating desktop entry for {app_name}...",
            )

        try:
            from .desktop_entry import create_desktop_entry_for_app

            create_desktop_entry_for_app(
                app_name=app_name,
                appimage_path=appimage_path,
                icon_path=icon_path,
                comment=f"{app_name.title()} AppImage Application",
                categories=["Utility"],
                config_manager=self.config_manager,
            )
        except Exception as e:
            logger.warning("⚠️  Failed to update desktop entry: %s", e)

    def _get_stored_hash(
        self,
        verification_results: dict[str, Any],
        appimage_asset: Asset,
    ) -> str:
        """Get the hash to store from verification results or asset digest."""
        if verification_results.get("digest", {}).get("passed"):
            return verification_results["digest"]["hash"]
        elif verification_results.get("checksum_file", {}).get("passed"):
            return verification_results["checksum_file"]["hash"]
        elif appimage_asset.digest:
            return appimage_asset.digest
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
        """Extract icon from AppImage or install from github.

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
        from .icon import IconConfig

        current_icon_config = app_config.get("icon", {}) if app_config else {}

        icon_config = IconConfig(
            extraction_enabled=True,  # Will be determined by service
            icon_url=icon_asset["icon_url"]
            if icon_asset["icon_url"]
            else None,
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
        asset: dict[str, Any],
        verification_config: dict[str, Any],
        owner: str,
        repo: str,
        tag_name: str,
        app_name: str,
        release_data: Release | None = None,
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
        logger.debug("   📦 Asset digest: %s", asset.digest or "None")

        if self.verification_service is None:
            raise RuntimeError("Verification service not initialized")

        logger.debug("🔄 About to call VerificationService.verify_file()")

        # Extract assets list from release_data if available
        # Convert Release assets to dict format for compatibility with verification
        assets_list = []
        if release_data and release_data.assets:
            # Convert Asset objects to dicts for verification service
            for asset_obj in release_data.assets:
                assets_list.append(
                    {
                        "name": asset_obj.name,
                        "size": asset_obj.size,
                        "browser_download_url": asset_obj.browser_download_url,
                        "digest": asset_obj.digest or "",
                    }
                )

        try:
            logger.debug("🔍 Calling VerificationService.verify_file() with:")
            logger.debug("   - asset: %s", asset)
            logger.debug("   - config: %s", verification_config)
            logger.debug("   - assets_list: %d items", len(assets_list))

            result = await self.verification_service.verify_file(
                file_path=path,
                asset=asset,
                config=verification_config,
                owner=owner,
                repo=repo,
                tag_name=tag_name,
                app_name=app_name,
                assets=assets_list,
                progress_task_id=progress_task_id,
            )

            logger.debug(
                "✅ VerificationService.verify_file() completed successfully"
            )
            logger.debug("   - result.passed: %s", result.passed)
            logger.debug(
                "   - result.methods: %s", list(result.methods.keys())
            )

            return result.methods, result.updated_config

        except Exception as e:
            logger.error("❌ VerificationService.verify_file() failed: %s", e)
            logger.error("   - Exception type: %s", type(e).__name__)
            import traceback

            logger.debug("   - Traceback: %s", traceback.format_exc())
            raise

    async def update_multiple_apps(
        self,
        app_names: list[str],
        force: bool = False,
        update_infos: list[UpdateInfo] | None = None,
    ) -> dict[str, bool]:
        """Update multiple apps.

        Args:
            app_names: List of app names to update
            force: Force update even if no new version available
            update_infos: Optional pre-fetched update info objects with cached
                release data

        Returns:
            Dictionary mapping app names to success status

        """
        semaphore = asyncio.Semaphore(
            self.global_config["max_concurrent_downloads"]
        )
        results = {}

        # Create lookup map for update infos
        update_info_map = {}
        if update_infos:
            update_info_map = {info.app_name: info for info in update_infos}
            logger.debug(
                "Using cached update info for %d apps (eliminates cache re-reads)",
                len(update_info_map),
            )

        async with aiohttp.ClientSession() as session:

            async def update_with_semaphore(app_name: str) -> tuple[str, bool]:
                async with semaphore:
                    # Use cached update info if available
                    cached_info = update_info_map.get(app_name)
                    success = await self.update_single_app(
                        app_name, session, force, cached_info
                    )
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
