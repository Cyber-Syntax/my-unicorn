"""Update management for installed AppImage applications.

This module handles checking for updates, downloading new versions,
and managing the update process for installed AppImages.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import aiohttp
from packaging.version import InvalidVersion, Version

from my_unicorn.config import ConfigManager
from my_unicorn.config.migration.helpers import warn_about_migration
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
from my_unicorn.core.workflows.appimage_setup import (
    create_desktop_entry,
    rename_appimage,
    setup_appimage_icon,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_utils import (
    select_best_appimage_asset,
    verify_appimage_download,
)

logger = get_logger(__name__)


@dataclass
class UpdateInfo:
    """Information about an available update.

    This class now includes in-memory caching of release data AND loaded config
    to eliminate redundant cache file reads and config validation during a single
    update operation.
    """

    app_name: str
    current_version: str = "unknown"
    latest_version: str = "unknown"
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
        if not self.original_tag_name and self.latest_version != "unknown":
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
    """Manages updates for installed AppImages."""

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        auth_manager: GitHubAuthManager | None = None,
        progress_service: Any = None,
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

    @classmethod
    def create_default(
        cls,
        config_manager: ConfigManager | None = None,
        progress_service: Any = None,
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

    def _initialize_services(self, session: Any) -> None:
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
            except InvalidVersion:
                # Fall through to legacy comparison if parsing fails
                pass
            else:
                return latest_version > current_version

        # Legacy comparison for backward compatibility
        try:
            current_parts = [int(x) for x in current_clean.split(".")]
            latest_parts = [int(x) for x in latest_clean.split(".")]

            # Pad shorter version with zeros
            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
        except ValueError:
            # Fallback to string comparison
            return latest_clean > current_clean
        else:
            return latest_parts > current_parts

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
            # TODO: Decrease the config loads in this one by getting returns from the config manager?
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                logger.warning("No config found for app: %s", app_name)
                return UpdateInfo(
                    app_name=app_name,
                    error_reason="No config found for app",
                )

            # Get config (all configs are v2 after migration)
            # load_app_config now returns fully merged config
            current_version = app_config.get("state", {}).get(
                "version", "unknown"
            )
            source_config = app_config.get("source", {})
            owner = source_config.get("owner", "unknown")
            repo = source_config.get("repo", "unknown")
            should_use_prerelease = source_config.get("prerelease", False)

            logger.debug(
                "Checking updates for %s (%s/%s)", app_name, owner, repo
            )

            # NOTE: Catalog apps are optimized to avoid duplicate API calls:
            # - If catalog specifies prerelease=true, we call fetch_latest_prerelease() directly (1 API call)
            # - If catalog specifies prerelease=false, we call fetch_latest_release_or_prerelease()
            #   which tries stable first (/releases/latest), then fallbacks to prerelease only if needed
            #
            # For URL installs (apps without catalog entries):
            # - Must use fetch_latest_release_or_prerelease(prefer_prerelease=False) fallback pattern
            # - This may result in 2 API calls for prerelease-only repos (try stable, then prerelease)
            # - This is a known limitation due to GitHub API design (/releases/latest only returns stable)
            #
            # The release_data is cached in UpdateInfo.release_data for reuse in update_single_app()
            # to avoid redundant API calls within the same operation.
            #
            # Fetch latest release
            fetcher = ReleaseFetcher(owner, repo, session, self.auth_manager)
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

            # Cache release data AND app_config in UpdateInfo for in-memory reuse within single operation
            # This eliminates redundant cache file reads and config validation in subsequent update phases
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
                app_config=app_config,  # Store loaded config to avoid re-validation
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
                error_reason=f"Unexpected error: {e}",
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
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                msg = f"No config found for {app_name}"
                raise ValueError(msg)

        owner, repo, _ = extract_github_config(app_config)

        # Load catalog entry if referenced
        catalog_ref = app_config.get("catalog_ref")
        catalog_entry = None
        if catalog_ref:
            try:
                catalog_entry = self.config_manager.load_catalog(catalog_ref)
            except (FileNotFoundError, ValueError):
                msg = (
                    f"App '{app_name}' references catalog '{catalog_ref}', "
                    f"but catalog entry is missing or invalid. Please reinstall."
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

        def _raise_invalid_update_info() -> None:
            msg = "update_info from context is guaranteed to be non-None"
            raise ValueError(msg)

        def _raise_no_release_data() -> None:
            msg = "release_data must be available"
            raise ValueError(msg)

        try:
            # Prepare update context
            context, error = await self._prepare_update_context(
                app_name, session, force, update_info
            )
            if error or context is None:
                return False, error
            if context.get("skip"):
                return True, None

            # Extract from context
            app_config = context["app_config"]
            update_info = cast("UpdateInfo", context["update_info"])
            appimage_asset = context["appimage_asset"]

            # Type narrowing: update_info from context is guaranteed
            # to be non-None and successful (checked in _prepare_update_context)

            # Setup paths
            storage_dir = Path(self.global_config["directory"]["storage"])
            icon_dir = Path(self.global_config["directory"]["icon"])
            download_dir = Path(self.global_config["directory"]["download"])

            # Get download path

            download_service_temp = DownloadService(None)  # type: ignore[arg-type]
            filename = download_service_temp.get_filename_from_url(
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
            # (checked in _prepare_update_context)
            if update_info.release_data is None:
                _raise_no_release_data()
            success = await self._process_post_download(
                app_name=app_name,
                app_config=app_config,
                update_info=update_info,
                owner=context["owner"],
                repo=context["repo"],
                catalog_entry=context["catalog_entry"],
                appimage_asset=appimage_asset,
                release_data=update_info.release_data,  # type: ignore[arg-type]
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
                return True, None
            return False, "Post-download processing failed"

        except Exception as e:
            logger.exception("Failed to update %s", app_name)
            return False, f"Update failed: {e}"

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
        progress_service = self._progress_service_param
        progress_enabled = (
            progress_service is not None and progress_service.is_active()
        )

        # Ensure these are defined prior to operations to avoid
        # referencing them in exception handlers where they may
        # otherwise be undefined.
        verification_task_id = None
        installation_task_id = None

        def _raise_no_progress_service() -> None:
            msg = "Progress service is required when progress is enabled"
            raise ValueError(msg)

        def _raise_no_verification_service() -> None:
            msg = "verification_service must be initialized"
            raise ValueError(msg)

        def _raise_progress_required() -> None:
            msg = "Progress service is required"
            raise ValueError(msg)

        try:
            if progress_enabled:
                # Type narrowing: progress_enabled is only True when
                # progress_service is not None
                if progress_service is None:
                    _raise_no_progress_service()
                (
                    verification_task_id,
                    installation_task_id,
                ) = await progress_service.create_installation_workflow(
                    app_name, with_verification=True
                )

            # Verify download if requested
            # verification_service is initialized in _initialize_services called before this method
            if self.verification_service is None:
                _raise_no_verification_service()
            verify_result = await verify_appimage_download(
                file_path=downloaded_path,
                asset=appimage_asset,
                release=release_data,
                app_name=app_name,
                verification_service=self.verification_service,  # type: ignore[arg-type]
                verification_config=app_config.get("verification"),
                catalog_entry=catalog_entry,
                owner=owner,
                repo=repo,
                progress_task_id=verification_task_id,
            )
            verification_results = verify_result.get("methods", {})
            updated_verification_config = verify_result.get(
                "updated_config", {}
            )

            # Move to install directory and make executable

            self.storage_service.make_executable(downloaded_path)
            appimage_path = self.storage_service.move_to_install_dir(
                downloaded_path
            )

            # Rename to clean name using catalog configuration
            appimage_path = rename_appimage(
                appimage_path=appimage_path,
                app_name=app_name,
                app_config=app_config,
                catalog_entry=catalog_entry,
                storage_service=self.storage_service,
            )

            # Handle icon setup
            icon_result = await setup_appimage_icon(
                appimage_path=appimage_path,
                app_name=app_name,
                icon_dir=icon_dir,
                app_config=app_config,
                catalog_entry=catalog_entry,
            )
            icon_path = (
                Path(icon_result["path"]) if icon_result.get("path") else None
            )
            updated_icon_config = {
                "source": icon_result.get("source", "none"),
                "installed": icon_result.get("installed", False),
                "path": icon_result.get("path"),
                "extraction": icon_result.get("extraction", False),
                "name": icon_result.get("name", ""),
            }

            # Update configuration
            await self._handle_configuration_update(
                app_name,
                app_config,
                update_info,
                appimage_path,
                icon_path,
                verification_results,
                updated_verification_config,
                updated_icon_config,
            )

            # Create desktop entry
            try:
                create_desktop_entry(
                    appimage_path=appimage_path,
                    app_name=app_name,
                    icon_result={
                        "icon_path": str(icon_path) if icon_path else None,
                        "path": str(icon_path) if icon_path else None,
                    },
                    config_manager=self.config_manager,
                )
            except Exception:
                logger.exception(
                    "Failed to update desktop entry for %s", app_name
                )

            # Finish installation task
            if installation_task_id and progress_enabled:
                if progress_service is None:
                    _raise_progress_required()
                await progress_service.finish_task(
                    installation_task_id,
                    success=True,
                    description=f"✅ {app_name}",
                )

            # Store the computed hash
            stored_hash = self._get_stored_hash(
                verification_results, appimage_asset
            )
            if stored_hash:
                logger.debug("Updated stored hash: %s", stored_hash[:16])

            return True

        except Exception:
            # Mark installation as failed if we have a progress task
            if installation_task_id and progress_enabled:
                if progress_service is None:
                    _raise_progress_required()
                await progress_service.finish_task(
                    installation_task_id,
                    success=False,
                    description=f"❌ {app_name} installation failed",
                )
            raise  # Re-raise the exception to be handled by the main method

    async def _handle_configuration_update(
        self,
        app_name: str,
        app_config: dict[str, Any],
        update_info: UpdateInfo,
        appimage_path: Path,
        icon_path: Path | None,
        verification_results: dict[str, Any],
        updated_verification_config: dict[str, Any],
        updated_icon_config: dict[str, Any],
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

        """
        # Load raw state for modification (not merged effective config)
        raw_state = self.config_manager.load_raw_app_config(app_name)
        if not raw_state:
            msg = f"Cannot update config: app state not found for {app_name}"
            raise ValueError(msg)

        # Store computed hash (will be empty dict if no asset provided)
        stored_hash = ""
        if verification_results.get("digest", {}).get("passed"):
            stored_hash = verification_results["digest"]["hash"]
        elif verification_results.get("checksum_file", {}).get("passed"):
            stored_hash = verification_results["checksum_file"]["hash"]

        # Update state fields (v2 format)
        if "state" not in raw_state:
            raw_state["state"] = {}
        raw_state["state"]["version"] = update_info.latest_version
        raw_state["state"]["installed_path"] = str(appimage_path)
        raw_state["state"]["installed_date"] = (
            datetime.now().astimezone().isoformat()
        )
        # Note: Verification results are stored in state.verification during install

        # Update icon configuration in state.icon (v2 format)
        if updated_icon_config:
            # Map workflow utility result to v2 schema format
            # v2 schema only allows: installed, method, path
            raw_state["state"]["icon"] = {
                "installed": updated_icon_config.get("installed", False),
                "method": updated_icon_config.get("source", "none"),
                "path": updated_icon_config.get("path", ""),
            }

            if icon_path:
                logger.debug(
                    "🎨 Icon updated for %s: method=%s, installed=%s",
                    app_name,
                    raw_state["state"]["icon"]["method"],
                    raw_state["state"]["icon"]["installed"],
                )

        self.config_manager.save_app_config(
            app_name, raw_state, skip_validation=True
        )

        # Clean up old backups after successful update
        try:
            self.backup_service.cleanup_old_backups(app_name)
        except Exception as e:
            logger.warning(
                "⚠️  Failed to cleanup old backups for %s: %s",
                app_name,
                e,
            )

    def _get_stored_hash(
        self,
        verification_results: dict[str, Any],
        appimage_asset: Asset,
    ) -> str:
        """Get the hash to store from verification results or asset digest."""
        if verification_results.get("digest", {}).get("passed"):
            return str(verification_results["digest"]["hash"])
        if verification_results.get("checksum_file", {}).get("passed"):
            return str(verification_results["checksum_file"]["hash"])
        if appimage_asset.digest:
            return appimage_asset.digest
        return ""

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
        except Exception:
            pass

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
                    error_reasons["unknown"] = f"Task failed: {result}"

        return results, error_reasons
