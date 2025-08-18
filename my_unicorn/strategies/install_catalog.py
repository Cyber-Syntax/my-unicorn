"""Catalog-based installation strategy.

This module implements the strategy for installing AppImages from the application catalog.
"""

import asyncio
from pathlib import Path
from typing import Any

from ..logger import get_logger
from my_unicorn.download import IconAsset
from .install_url import InstallationError, InstallStrategy, ValidationError

logger = get_logger(__name__)


class CatalogInstallStrategy(InstallStrategy):
    """Strategy for installing AppImages from the catalog."""

    def __init__(
        self, catalog_manager: Any, github_client: Any, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize catalog install strategy.

        Args:
            catalog_manager: Catalog manager for app lookup
            github_client: GitHub client for API access
            *args: Arguments passed to parent class
            **kwargs: Keyword arguments passed to parent class

        """
        super().__init__(*args, **kwargs)
        self.catalog_manager = catalog_manager
        self.github_client = github_client

    def validate_targets(self, targets: list[str]) -> None:
        """Validate that targets are valid catalog app names.

        Args:
            targets: List of application names from catalog

        Raises:
            ValidationError: If any target is not found in catalog

        """
        available_apps = self.catalog_manager.get_available_apps()

        for target in targets:
            if target not in available_apps:
                raise ValidationError(
                    f"Application '{target}' not found in catalog. "
                    f"Available apps: {', '.join(sorted(available_apps.keys()))}"
                )

    async def install(self, targets: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        """Install applications from catalog.

        Args:
            targets: List of application names from catalog
            **kwargs: Additional options including:
                - concurrent: Maximum concurrent installations
                - show_progress: Whether to show progress bars
                - verify_downloads: Whether to verify downloads

        Returns:
            List of installation results

        """
        self.validate_targets(targets)

        concurrent = kwargs.get("concurrent", 3)
        semaphore = asyncio.Semaphore(concurrent)

        tasks = [
            self._install_single_app(semaphore, app_name, **kwargs) for app_name in targets
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "target": targets[i],
                        "success": False,
                        "error": str(result),
                        "path": None,
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _install_single_app(
        self, semaphore: asyncio.Semaphore, app_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Install a single application from catalog.

        Args:
            semaphore: Semaphore for concurrency control
            app_name: Name of application to install
            **kwargs: Installation options

        Returns:
            Installation result dictionary

        """
        async with semaphore:
            try:
                logger.info(f"🚀 Installing from catalog: {app_name}")

                # Get app configuration from catalog
                app_config = self.catalog_manager.get_app_config(app_name)
                logger.debug(f"App config for {app_name}: {app_config}")
                if not app_config:
                    raise InstallationError(f"App configuration not found: {app_name}")

                # Check for existing installation
                existing_path = await self._handle_existing_installation(
                    app_name, app_config, **kwargs
                )
                if existing_path:
                    return {
                        "target": app_name,
                        "success": True,
                        "path": str(existing_path),
                        "name": existing_path.name,
                        "source": "catalog",
                        "status": "already_installed",
                    }

                # Get release configuration
                release_config = self._get_release_config(app_config)
                logger.debug(f"Release config: {release_config}")

                # Fetch release data from GitHub
                logger.info(f"📡 Fetching release data for {app_name}")
                release_data = await self._fetch_release_data(release_config)
                logger.debug(f"Release data: {release_data}")

                # Find AppImage asset using characteristic_suffix from catalog config
                characteristic_suffix = app_config.get("appimage", {}).get(
                    "characteristic_suffix", []
                )

                # Create a GitHubReleaseFetcher to use its select_best_appimage method
                from ..github_client import GitHubReleaseFetcher

                owner = release_config.get("owner")
                repo = release_config.get("repo")
                fetcher = GitHubReleaseFetcher(owner, repo, self.session)

                appimage_asset = fetcher.select_best_appimage(
                    release_data, characteristic_suffix
                )
                if not appimage_asset:
                    raise InstallationError(
                        f"No AppImage found for {app_name} with characteristic_suffix: {characteristic_suffix}"
                    )

                # Setup paths
                download_dir = kwargs.get("download_dir", Path.cwd())
                filename = self.download_service.get_filename_from_url(
                    appimage_asset["browser_download_url"]
                )
                download_path = download_dir / filename

                # Download AppImage
                appimage_path = await self.download_service.download_appimage(
                    appimage_asset,
                    download_path,
                    show_progress=kwargs.get("show_progress", True),
                )

                # Verify download if requested
                if kwargs.get("verify_downloads", True):
                    await self._perform_verification(
                        download_path, appimage_asset, app_config, release_data
                    )

                # Move to install directory
                final_path = self.storage_service.move_to_install_dir(download_path)

                # Make executable
                self.storage_service.make_executable(final_path)

                # Handle renaming based on catalog config
                if rename_config := app_config.get("appimage", {}).get("rename"):
                    clean_name = self.storage_service.get_clean_appimage_name(rename_config)
                    final_path = self.storage_service.rename_appimage(final_path, clean_name)

                # Get icon directory from global config (needed for both icon download and config creation)
                from ..config import ConfigManager

                config_manager = ConfigManager()
                global_config = config_manager.load_global_config()
                icon_dir = global_config["directory"]["icon"]

                # Download icon if configured
                icon_path = None
                if app_config.get("icon"):
                    icon_path = await self._setup_catalog_icon(app_config, app_name, icon_dir)

                # Create application configuration
                self._create_app_config(
                    app_name, final_path, app_config, release_data, icon_dir, appimage_asset
                )
                
                # Create desktop entry to reflect any changes (icon, paths, etc.)
                try:
                    try:
                        from ..desktop import create_desktop_entry_for_app
                    except ImportError:
                        from ..desktop import create_desktop_entry_for_app
    
                    desktop_path = create_desktop_entry_for_app(
                        app_name=app_name,
                        appimage_path=final_path,
                        icon_path=icon_path,
                        comment=f"{app_name.title()} AppImage Application",
                        categories=["Utility"],
                        config_manager=config_manager,
                    )
                    # Desktop entry creation/update logging is handled by the desktop module
                except Exception as e:
                    logger.warning(f"⚠️  Failed to update desktop entry: {e}")

                logger.info(f"✅ Successfully installed from catalog: {final_path}")

                return {
                    "target": app_name,
                    "success": True,
                    "path": str(final_path),
                    "name": final_path.name,
                    "source": "catalog",
                    "version": release_data.get("tag_name"),
                    "icon_path": str(icon_path) if icon_path else None,
                }

            except Exception as e:
                logger.error(f"❌ Failed to install {app_name}: {e}")
                import traceback

                logger.debug(f"Full traceback: {traceback.format_exc()}")
                return {
                    "target": app_name,
                    "success": False,
                    "error": str(e),
                    "path": None,
                }

    async def _handle_existing_installation(
        self, app_name: str, app_config: dict[str, Any], **kwargs: Any
    ) -> Path | None:
        """Handle existing installation if present.

        Args:
            app_name: Application name
            app_config: Application configuration from catalog
            **kwargs: Installation options

        Returns:
            Path to existing installation or None if should proceed with new install

        """
        # Check if app is already installed
        existing_config = self.catalog_manager.get_installed_app_config(app_name)
        if not existing_config:
            return None

        existing_path = Path(existing_config.get("path", ""))
        if not existing_path.exists():
            logger.debug(f"📝 Removing stale config for {app_name}")
            self.catalog_manager.remove_app_config(app_name)
            return None

        # Check for force reinstall
        if kwargs.get("force", False):
            logger.info(f"🔄 Force reinstalling {app_name}")
            return None

        # Check for updates if update mode
        if kwargs.get("update", False):
            logger.info(f"🔄 Checking for updates for {app_name}")
            # TODO: Implement update check logic
            return None

        logger.info(f"✅ {app_name} is already installed at {existing_path}")
        return existing_path

    def _get_release_config(self, app_config: dict[str, Any]) -> dict[str, Any]:
        """Extract release configuration from app config.

        Args:
            app_config: Application configuration

        Returns:
            Release configuration dictionary

        """
        return {
            "owner": app_config.get("owner"),
            "repo": app_config.get("repo"),
            "tag": app_config.get("tag"),  # Optional specific tag
        }

    async def _fetch_release_data(self, release_config: dict[str, Any]) -> dict[str, Any]:
        """Fetch release data from GitHub.

        Args:
            release_config: Release configuration

        Returns:
            GitHub release data

        Raises:
            InstallationError: If release data cannot be fetched

        """
        owner = release_config.get("owner")
        repo = release_config.get("repo")
        tag = release_config.get("tag")

        if not owner or not repo:
            raise InstallationError("Invalid GitHub configuration: missing owner or repo")

        try:
            if tag:
                release_data = await self.github_client.get_release_by_tag(owner, repo, tag)
            else:
                release_data = await self.github_client.get_latest_release(owner, repo)

            if not release_data:
                raise InstallationError(f"No release found for {owner}/{repo}")

            return release_data

        except Exception as e:
            raise InstallationError(f"Failed to fetch release data: {e}")

    async def _perform_verification(
        self,
        path: Path,
        asset: dict[str, Any],
        app_config: dict[str, Any],
        release_data: dict[str, Any],
    ) -> None:
        """Perform download verification based on catalog configuration.

        Args:
            path: Path to downloaded file
            asset: GitHub asset information
            app_config: Application configuration from catalog
            release_data: GitHub release data

        Raises:
            InstallationError: If verification fails

        """
        from ..verify import Verifier

        # Get verification configuration from catalog
        verification_config = app_config.get("verification", {})

        # Skip verification if configured
        if verification_config.get("skip", False):
            logger.debug("⏭️ Verification skipped (configured in catalog)")
            return

        logger.debug(f"🔍 Starting verification for {path.name}")
        verifier = Verifier(path)
        verification_passed = False

        # Try digest verification first if enabled and available
        if verification_config.get("digest", False) and asset.get("digest"):
            try:
                logger.debug("🔐 Attempting digest verification")
                verifier.verify_digest(asset["digest"])
                logger.debug("✅ Digest verification passed")
                verification_passed = True
            except Exception as e:
                logger.error(f"❌ Digest verification failed: {e}")
                # Continue to try other verification methods

        # Try checksum file verification if configured and digest didn't pass
        if not verification_passed and verification_config.get("checksum_file"):
            checksum_file = verification_config["checksum_file"]
            hash_type = verification_config.get("checksum_hash_type", "sha256")

            # Build checksum URL using original tag name (preserves 'v' prefix)
            original_tag_name = release_data.get(
                "original_tag_name", release_data.get("tag_name", "")
            )
            owner = app_config.get("owner", "")
            repo = app_config.get("repo", "")
            checksum_url = f"https://github.com/{owner}/{repo}/releases/download/{original_tag_name}/{checksum_file}"

            try:
                logger.debug(f"🔍 Attempting checksum file verification: {checksum_file}")
                await verifier.verify_from_checksum_file(
                    checksum_url, hash_type, self.download_service, path.name
                )
                logger.debug("✅ Checksum file verification passed")
                verification_passed = True
            except Exception as e:
                logger.error(f"❌ Checksum file verification failed: {e}")
                # Continue to basic file size check

        # Always perform basic file size verification
        try:
            expected_size = asset.get("size", 0)
            if expected_size > 0:
                if not self.download_service.verify_file_size(path, expected_size):
                    raise InstallationError("File size verification failed")
                logger.debug("✅ File size verification passed")
            else:
                logger.debug("⚠️ No expected file size available, skipping size verification")
        except Exception as e:
            logger.error(f"❌ File size verification failed: {e}")
            if not verification_passed:
                raise InstallationError("File verification failed")

        # If we have verification methods configured but none passed, fail
        if (
            verification_config.get("digest", False)
            or verification_config.get("checksum_file")
        ) and not verification_passed:
            raise InstallationError("Configured verification methods failed")

        logger.debug("✅ Verification completed")

    async def _setup_catalog_icon(
        self, app_config: dict[str, Any], app_name: str, icon_dir: Path
    ) -> Path | None:
        """Setup icon from catalog configuration.

        Args:
            app_config: Application configuration
            app_name: Application name for icon filename
            icon_dir: Directory where icons should be saved

        Returns:
            Path to downloaded icon or None

        """
        icon_config = app_config.get("icon", {})
        if not icon_config:
            return None

        icon_url = icon_config.get("url")
        if not icon_url:
            return None

        # Use the icon name from catalog config if available, otherwise generate one
        icon_filename = icon_config.get("name")
        if not icon_filename:
            icon_extension = icon_config.get("extension", "png")
            icon_filename = f"{app_name}.{icon_extension}"

        icon_asset: IconAsset = {
            "icon_filename": icon_filename,
            "icon_url": icon_url,
        }

        icon_path = icon_dir / icon_filename

        try:
            return await self.download_service.download_icon(icon_asset, icon_path)
        except Exception as e:
            logger.warning(f"⚠️  Failed to download icon for {app_name}: {e}")
            return None

    def _create_app_config(
        self,
        app_name: str,
        app_path: Path,
        catalog_config: dict[str, Any],
        release_data: dict[str, Any],
        icon_dir: Path,
        appimage_asset: dict[str, Any] | None = None,
    ) -> None:
        """Create application configuration after successful installation.

        Args:
            app_name: Application name
            app_path: Path to installed application
            catalog_config: Original catalog configuration
            release_data: GitHub release data
            icon_dir: Directory where icons are stored
            appimage_asset: AppImage asset info for digest

        """
        # Extract appimage config from catalog config
        appimage_config = catalog_config.get("appimage", {})

        config = {
            "config_version": "1.0.0",
            "source": "catalog",
            "appimage": {
                "version": release_data.get("tag_name", "unknown"),
                "name": app_path.name,
                "rename": appimage_config.get("rename", app_name),
                "name_template": appimage_config.get("name_template", ""),
                "characteristic_suffix": appimage_config.get("characteristic_suffix", []),
                "installed_date": self._get_current_timestamp(),
                "digest": appimage_asset.get("digest", "") if appimage_asset else "",
            },
            "owner": catalog_config.get("owner", ""),
            "repo": catalog_config.get("repo", ""),
            "github": catalog_config.get("github", {"repo": True, "prerelease": False}),
            "verification": catalog_config.get(
                "verification",
                {
                    "digest": True,
                    "skip": False,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
            ),
            "icon": catalog_config.get("icon", {}),
        }

        # Add icon path if available
        icon_config = catalog_config.get("icon", {})
        if icon_config:
            # Use the icon name from catalog config
            icon_filename = icon_config.get("name")
            if not icon_filename:
                icon_extension = icon_config.get("extension", "png")
                icon_filename = f"{app_name}.{icon_extension}"

            icon_path = icon_dir / icon_filename
            if icon_path.exists():
                config["icon"]["path"] = str(icon_path)

        self.catalog_manager.save_app_config(app_name, config)
        logger.debug(f"📝 Saved configuration for {app_name}")

    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string.

        Returns:
            Current timestamp in ISO format

        """
        from datetime import datetime

        return datetime.now().isoformat()
