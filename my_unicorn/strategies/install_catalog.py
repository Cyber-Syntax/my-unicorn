"""Catalog-based installation strategy.

This module implements the strategy for installing AppImages from the application catalog.
"""

import asyncio
from pathlib import Path
from typing import Any

from ..logger import get_logger
from ..services import IconConfig, IconService, VerificationService
from ..utils import extract_and_validate_version
from .install_url import InstallationError, InstallStrategy, ValidationError

logger = get_logger(__name__)


class CatalogInstallStrategy(InstallStrategy):
    """Strategy for installing AppImages from the catalog."""

    def __init__(
        self,
        catalog_manager: Any,
        config_manager: Any,
        github_client: Any,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize catalog install strategy.

        Args:
            catalog_manager: Catalog manager for app lookup
            config_manager: Configuration manager for app configs
            github_client: GitHub client for API access
            *args: Arguments passed to parent class
            **kwargs: Keyword arguments passed to parent class

        """
        # Extract parent class parameters from kwargs
        download_service = kwargs.pop("download_service")
        storage_service = kwargs.pop("storage_service")
        session = kwargs.pop("session")

        super().__init__(
            download_service=download_service,
            storage_service=storage_service,
            session=session,
            config_manager=config_manager,
        )
        self.catalog_manager = catalog_manager
        self.github_client = github_client

        # Initialize shared services
        self.icon_service = IconService(download_service)
        self.verification_service = VerificationService(download_service)

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

        semaphore = asyncio.Semaphore(self.global_config["max_concurrent_downloads"])

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
                logger.info("🚀 Installing from catalog: %s", app_name)

                # Get app configuration from catalog
                app_config = self.catalog_manager.get_app_config(app_name)
                logger.debug("App config for %s: %s", app_name, app_config)
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
                logger.debug("Release config: %s", release_config)

                # Fetch release data from GitHub
                logger.info("📡 Fetching release data for %s", app_name)
                release_data = await self._fetch_release_data(release_config)
                logger.debug("Release data: %s", release_data)

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
                    verification_result = await self._perform_verification(
                        download_path, appimage_asset, app_config, release_data
                    )
                else:
                    verification_result = None

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

                # Get icon using new IconManager (AppImage extraction + GitHub fallback)
                icon_path = None
                updated_icon_config = {}
                if (
                    app_config.get("icon") or True
                ):  # Always try extraction even without icon config
                    icon_path, updated_icon_config = await self._setup_catalog_icon(
                        app_config, app_name, icon_dir, final_path
                    )

                # Create application configuration (pass verification result for config updates)
                self._create_app_config(
                    app_name,
                    final_path,
                    app_config,
                    release_data,
                    icon_dir,
                    appimage_asset,
                    verification_result,
                    updated_icon_config,
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
                    logger.warning("⚠️  Failed to update desktop entry: %s", e)

                logger.info("✅ Successfully installed from catalog: %s", final_path)

                return {
                    "target": app_name,
                    "success": True,
                    "path": str(final_path),
                    "name": final_path.name,
                    "source": "catalog",
                    "version": extract_and_validate_version(release_data.get("tag_name", "")),
                    "icon_path": str(icon_path) if icon_path else None,
                }

            except Exception as e:
                logger.error("❌ Failed to install %s: %s", app_name, e)
                import traceback

                logger.debug("Full traceback: %s", traceback.format_exc())
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
            logger.debug("📝 Removing stale config for %s", app_name)
            self.catalog_manager.remove_app_config(app_name)
            return None

        # Check for force reinstall
        if kwargs.get("force", False):
            logger.info("🔄 Force reinstalling %s", app_name)
            return None

        # Check for updates if update mode
        if kwargs.get("update", False):
            logger.info("🔄 Checking for updates for %s", app_name)
            # TODO: Implement update check logic
            return None

        logger.info("✅ %s is already installed at %s", app_name, existing_path)
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
    ) -> dict[str, Any]:
        """Perform download verification based on catalog configuration.

        Args:
            path: Path to downloaded file
            asset: GitHub asset information
            app_config: Application configuration from catalog
            release_data: GitHub release data

        Returns:
            Dictionary containing successful verification methods and updated config

        Raises:
            InstallationError: If verification fails

        """
        # Get verification configuration from catalog
        verification_config = app_config.get("verification", {})

        # Get repository info
        owner = app_config.get("owner", "")
        repo = app_config.get("repo", "")
        original_tag_name = release_data.get(
            "original_tag_name", release_data.get("tag_name", "")
        )

        try:
            result = await self.verification_service.verify_file(
                file_path=path,
                asset=asset,
                config=verification_config,
                owner=owner,
                repo=repo,
                tag_name=original_tag_name,
                app_name=path.name,
                assets=release_data.get("assets", []),
            )

            return {
                "successful_methods": result.methods,
                "updated_config": result.updated_config,
            }
        except Exception as e:
            raise InstallationError(str(e)) from e

    async def _setup_catalog_icon(
        self, app_config: dict[str, Any], app_name: str, icon_dir: Path, appimage_path: Path
    ) -> tuple[Path | None, dict[str, Any]]:
        """Setup icon from catalog configuration using shared IconService.

        Args:
            app_config: Application configuration
            app_name: Application name for icon filename
            icon_dir: Directory where icons should be saved
            appimage_path: Path to AppImage for icon extraction

        Returns:
            Tuple of (Path to acquired icon or None, updated icon config)

        """
        icon_config_dict = app_config.get("icon", {})

        # Check if extraction is enabled (default True)
        extraction_enabled = icon_config_dict.get("extraction", True)
        icon_url = icon_config_dict.get("url", "")

        # Generate filename if not provided
        icon_filename = icon_config_dict.get("name")
        if not icon_filename:
            icon_filename = self.icon_service._generate_icon_filename(app_name, icon_url)

        # Create icon configuration

        icon_config = IconConfig(
            extraction_enabled=extraction_enabled,
            icon_url=icon_url if icon_url else None,
            icon_filename=icon_filename,
            preserve_url_on_extraction=False,  # Clear URL on extraction for catalog
        )

        # Use shared service to acquire icon
        result = await self.icon_service.acquire_icon(
            icon_config=icon_config,
            app_name=app_name,
            icon_dir=icon_dir,
            appimage_path=appimage_path,
            current_config=icon_config_dict,
        )

        return result.icon_path, result.config

    def _create_app_config(
        self,
        app_name: str,
        app_path: Path,
        catalog_config: dict[str, Any],
        release_data: dict[str, Any],
        icon_dir: Path,
        appimage_asset: dict[str, Any] | None = None,
        verification_result: dict[str, Any] | None = None,
        updated_icon_config: dict[str, Any] | None = None,
    ) -> None:
        """Create application configuration after successful installation.

        Args:
            app_name: Application name
            app_path: Path to installed application
            catalog_config: Original catalog configuration
            release_data: GitHub release data
            icon_dir: Directory where icons are stored
            appimage_asset: AppImage asset info for digest
            verification_result: Result from verification with updated config

        """
        # Extract appimage config from catalog config
        appimage_config = catalog_config.get("appimage", {})

        config = {
            "config_version": "1.0.0",
            "source": "catalog",
            "appimage": {
                "version": extract_and_validate_version(release_data.get("tag_name", ""))
                or "unknown",
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
            "verification": self._get_updated_verification_config(
                catalog_config, verification_result
            ),
            "icon": updated_icon_config or catalog_config.get("icon", {}),
        }

        # Add icon path if available
        final_icon_config = updated_icon_config or catalog_config.get("icon", {})
        if final_icon_config:
            icon_filename = final_icon_config.get("name")
            if icon_filename:
                icon_path = icon_dir / icon_filename
                if icon_path.exists():
                    config["icon"]["path"] = str(icon_path)

        self.catalog_manager.save_app_config(app_name, config)

        # Log verification config updates if any
        if verification_result and verification_result.get("successful_methods"):
            methods = list(verification_result["successful_methods"].keys())
            logger.debug(
                f"📝 Saved configuration for {app_name} with updated verification: {', '.join(methods)}"
            )
        else:
            logger.debug("📝 Saved configuration for %s", app_name)

    def _get_updated_verification_config(
        self, catalog_config: dict[str, Any], verification_result: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Get updated verification configuration based on successful verification methods.

        Args:
            catalog_config: Original catalog configuration
            verification_result: Result from verification process

        Returns:
            Updated verification configuration

        """
        # Start with catalog default or fallback
        verification_config = catalog_config.get(
            "verification",
            {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
        )

        # Update based on verification results if available
        if verification_result and verification_result.get("updated_config"):
            updated_config = verification_result["updated_config"]
            verification_config.update(updated_config)

            # Log what was updated
            if verification_result.get("successful_methods"):
                methods = list(verification_result["successful_methods"].keys())
                logger.debug(
                    f"🔧 Updated verification config based on successful methods: {', '.join(methods)}"
                )

        return verification_config

    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string.

        Returns:
            Current timestamp in ISO format

        """
        from datetime import datetime

        return datetime.now().isoformat()
