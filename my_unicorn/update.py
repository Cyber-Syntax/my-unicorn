"""Update management for installed AppImage applications.

This module handles checking for updates, downloading new versions,
and managing the update process for installed AppImages.
"""

import asyncio
from datetime import datetime

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
from .verify import Verifier

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

    def __init__(self, config_manager: ConfigManager | None = None):
        """Initialize update manager.

        Args:
            config_manager: Configuration manager instance

        """
        self.config_manager = config_manager or ConfigManager()
        self.global_config = self.config_manager.load_global_config()
        self.auth_manager = GitHubAuthManager()

        # Initialize storage service with install directory
        storage_dir = self.global_config["directory"]["storage"]
        self.storage_service = StorageService(storage_dir)

        # Initialize backup service
        self.backup_service = BackupService(self.config_manager, self.global_config)

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
                logger.warning(f"No config found for app: {app_name}")
                return None

            current_version = app_config["appimage"]["version"]
            owner = app_config["owner"]
            repo = app_config["repo"]

            logger.debug(f"Checking updates for {app_name} ({owner}/{repo})")

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
                logger.error(f"GitHub API disabled for {app_name} (github.repo: false)")
                return None

            # Fetch latest release
            fetcher = GitHubReleaseFetcher(owner, repo, session)
            if should_use_prerelease:
                logger.debug(f"Fetching latest prerelease for {owner}/{repo}")
                release_data = await fetcher.fetch_latest_prerelease()
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
            logger.error(f"Failed to check updates for {app_name}: {e}")
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
                logger.error(f"Update check failed: {result}")

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
        try:
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                logger.error(f"No config found for app: {app_name}")
                return False

            # Check for updates first
            update_info = await self.check_single_update(app_name, session)
            if not update_info:
                logger.error(f"Failed to check updates for {app_name}")
                return False

            if not force and not update_info.has_update:
                logger.debug(f"{app_name} is already up to date")
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
                logger.error(f"GitHub API disabled for {app_name} (github.repo: false)")
                return False

            fetcher = GitHubReleaseFetcher(owner, repo, session)
            if should_use_prerelease:
                logger.debug(f"Fetching latest prerelease for {owner}/{repo}")
                release_data = await fetcher.fetch_latest_prerelease()
            else:
                release_data = await fetcher.fetch_latest_release()

            # Find AppImage asset using source-aware selection
            appimage_asset = self._select_best_appimage_by_source(
                fetcher, release_data, app_config
            )

            if not appimage_asset:
                logger.error(f"No AppImage found for {app_name}")
                return False

            # Set up paths
            storage_dir = self.global_config["directory"]["storage"]
            backup_dir = self.global_config["directory"]["backup"]
            icon_dir = self.global_config["directory"]["icon"]
            download_dir = self.global_config["directory"]["download"]

            # Create backup of current version
            current_appimage_path = storage_dir / app_config["appimage"]["name"]
            if current_appimage_path.exists():
                backup_path = self.backup_service.create_backup(
                    current_appimage_path, backup_dir, update_info.current_version
                )
                if backup_path:
                    logger.debug(f"💾 Backup created: {backup_path}")

            # Download and install new version
            icon_asset = None
            if app_config.get("icon") and app_config["icon"].get("url"):
                icon_url = app_config["icon"]["url"]

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

                # Only create icon asset if we have a valid URL
                if icon_url:
                    icon_asset = IconAsset(
                        icon_filename=app_config["icon"]["name"],
                        icon_url=icon_url,
                    )

            # Initialize services for direct usage
            download_service = DownloadService(session)

            # Get clean name for renaming from catalog config if available
            catalog_entry = self.config_manager.load_catalog_entry(app_config["repo"].lower())
            rename_to = app_name  # fallback
            if catalog_entry and catalog_entry.get("appimage", {}).get("rename"):
                rename_to = catalog_entry["appimage"]["rename"]
            else:
                # Fallback to app config for backward compatibility
                rename_to = app_config["appimage"].get("rename", app_name)

            # Setup download path
            filename = download_service.get_filename_from_url(
                appimage_asset["browser_download_url"]
            )
            download_path = download_dir / filename

            # Download AppImage first (without renaming)
            appimage_path = await download_service.download_appimage(
                appimage_asset, download_path, show_progress=True
            )

            # Download icon if requested
            icon_path = None
            if bool(icon_asset):
                icon_full_path = icon_dir / icon_asset["icon_filename"]
                icon_path = await download_service.download_icon(icon_asset, icon_full_path)

            # Perform verification if configured (BEFORE renaming)
            verification_config = app_config.get("verification", {})
            verification_results = {}

            if not verification_config.get("skip", False):
                logger.debug(
                    f"🔍 Starting verification for updated {app_name} (original filename: {appimage_path.name})"
                )
                verifier = Verifier(appimage_path)

                # Try digest verification first (from GitHub API)
                if verification_config.get("digest", False) and appimage_asset.get("digest"):
                    try:
                        verifier.verify_digest(appimage_asset["digest"])
                        verification_results["digest"] = {
                            "passed": True,
                            "hash": appimage_asset["digest"],
                            "details": "GitHub API digest verification",
                        }
                        logger.debug("✅ Digest verification passed")
                    except Exception as e:
                        logger.error(f"❌ Digest verification failed: {e}")
                        verification_results["digest"] = {
                            "passed": False,
                            "hash": appimage_asset.get("digest", ""),
                            "details": str(e),
                        }

                # Try checksum file verification if configured
                elif verification_config.get("checksum_file"):
                    checksum_file = verification_config["checksum_file"]
                    hash_type = verification_config.get("checksum_hash_type", "sha256")
                    checksum_url = f"https://github.com/{owner}/{repo}/releases/download/{update_info.original_tag_name}/{checksum_file}"

                    try:
                        logger.debug(f"🔍 Verifying using checksum file: {checksum_file}")
                        # Use original filename for checksum verification
                        await verifier.verify_from_checksum_file(
                            checksum_url, hash_type, download_service, appimage_path.name
                        )
                        computed_hash = verifier.compute_hash(hash_type)
                        verification_results["checksum_file"] = {
                            "passed": True,
                            "hash": f"{hash_type}:{computed_hash}",
                            "details": f"Verified against {checksum_file}",
                        }
                        logger.debug("✅ Checksum file verification passed")
                    except Exception as e:
                        logger.error(f"❌ Checksum file verification failed: {e}")
                        verification_results["checksum_file"] = {
                            "passed": False,
                            "hash": "",
                            "details": str(e),
                        }

                # Basic file integrity check
                try:
                    file_size = verifier.get_file_size()
                    expected_size = appimage_asset.get("size", 0)
                    if expected_size > 0:
                        verifier.verify_size(expected_size)
                    verification_results["size"] = {
                        "passed": True,
                        "details": f"File size: {file_size:,} bytes",
                    }
                except Exception as e:
                    logger.warning(f"⚠️  Size verification failed: {e}")
                    verification_results["size"] = {"passed": False, "details": str(e)}

                logger.debug("✅ Verification completed")
            else:
                logger.debug(f"⏭️  Verification skipped for {app_name} (configured)")

            # Now make executable and move to install directory
            self.storage_service.make_executable(appimage_path)
            appimage_path = self.storage_service.move_to_install_dir(appimage_path)

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
            elif appimage_asset.get("digest"):
                stored_hash = appimage_asset["digest"]

            # Auto-detect digest availability and update verification config
            has_digest = bool(appimage_asset.get("digest"))
            if has_digest and not app_config.get("verification", {}).get("digest", False):
                logger.debug(
                    f"🔍 Digest now available for {app_name}, enabling digest verification"
                )
                logger.debug(f"   Digest: {appimage_asset.get('digest', '')}")
                app_config["verification"]["digest"] = True
                # If we now have digest, we can optionally disable checksum file verification
                if app_config["verification"].get("checksum_file"):
                    logger.debug("   Keeping checksum file verification as fallback")

            # Update app config
            app_config["appimage"]["version"] = update_info.latest_version
            app_config["appimage"]["name"] = appimage_path.name
            app_config["appimage"]["installed_date"] = datetime.now().isoformat()
            app_config["appimage"]["digest"] = stored_hash

            # Track if icon was updated for desktop entry regeneration
            icon_updated = False
            if icon_path:
                previous_icon_status = app_config.get("icon", {}).get("path") is not None
                if "icon" not in app_config:
                    app_config["icon"] = {}
                app_config["icon"]["path"] = str(icon_path)
                icon_updated = not previous_icon_status  # Icon was newly installed

            self.config_manager.save_app_config(app_name, app_config)

            # Clean up old backups after successful update
            try:
                self.backup_service.cleanup_old_backups(app_name)
            except Exception as e:
                logger.warning(f"⚠️  Failed to cleanup old backups for {app_name}: {e}")

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
                logger.warning(f"⚠️  Failed to update desktop entry: {e}")

            logger.debug(f"✅ Successfully updated {app_name} to {update_info.latest_version}")
            if stored_hash:
                logger.debug(f"🔐 Updated stored hash: {stored_hash}")
            return True

        except Exception as e:
            logger.error(f"Failed to update {app_name}: {e}")
            return False

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
                    logger.error(f"Update task failed: {result}")

        return results
