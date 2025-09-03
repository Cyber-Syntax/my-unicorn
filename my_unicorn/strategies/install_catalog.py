"""Catalog-based installation strategy.

This module implements the strategy for installing AppImages from the application catalog.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from my_unicorn.services.icon_service import IconConfig, IconService
from my_unicorn.services.verification_service import VerificationService

from ..github_client import GitHubAsset, GitHubReleaseDetails
from ..logger import get_logger
from ..utils import extract_and_validate_version
from .install import (
    InstallationError,
    InstallStrategy,
    ValidationError,
)

logger = get_logger(__name__)


# Catalog-specific progress tracking constants
class CatalogProgressSteps:
    """Constants for catalog-specific progress tracking percentages."""

    VERIFICATION_START = 10.0
    VERIFICATION_COMPLETE = 30.0
    MOVE_TO_INSTALL = 40.0
    ICON_START = 50.0
    ICON_COMPLETE = 70.0
    CONFIG_CREATE = 80.0
    DESKTOP_ENTRY = 90.0


@dataclass(frozen=True, slots=True)
class InstallationContext:
    """Context for a single catalog-based installation."""

    app_name: str
    download_path: Path
    app_config: dict[str, Any]
    release_data: dict[str, Any]
    appimage_asset: GitHubAsset
    post_processing_task_id: str | None = None
    final_path: Path | None = None

    @property
    def owner(self) -> str:
        """Get repository owner from app config."""
        return str(self.app_config.get("owner", ""))

    @property
    def repo(self) -> str:
        """Get repository name from app config."""
        return str(self.app_config.get("repo", ""))

    @property
    def verification_config(self) -> dict[str, Any]:
        """Get verification configuration from app config."""
        config = self.app_config.get("verification", {})
        return dict(config) if isinstance(config, dict) else {}


@dataclass(frozen=True, slots=True)
class AppConfigData:
    """Configuration data for creating app configuration."""

    app_name: str
    app_path: Path
    catalog_config: dict[str, Any]
    release_data: dict[str, Any]
    icon_dir: Path
    appimage_asset: GitHubAsset | None = None
    verification_result: dict[str, Any] | None = None
    updated_icon_config: dict[str, Any] | None = None


class CatalogInstallStrategy(InstallStrategy):
    """Strategy for installing AppImages from the catalog."""

    def __init__(
        self,
        catalog_manager: Any,
        config_manager: Any,
        github_client: Any,
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
        # Get progress service from download service if available
        progress_service = getattr(download_service, "progress_service", None)
        self.icon_service = IconService(download_service, progress_service)
        self.verification_service = VerificationService(download_service, progress_service)
        # progress_tracker is already initialized in base class

    def _get_icon_directory(self) -> Path:
        """Get icon directory from global configuration.

        Returns:
            Path to the icon directory

        """
        from ..config import ConfigManager

        config_manager = ConfigManager()
        global_config = config_manager.load_global_config()
        return global_config["directory"]["icon"]

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

        concurrent_limit = kwargs.get(
            "concurrent", self.global_config["max_concurrent_downloads"]
        )
        logger.info(
            "📚 Catalog install strategy using %d concurrent installations", concurrent_limit
        )
        semaphore = asyncio.Semaphore(concurrent_limit)

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

    async def _setup_installation_context(
        self, app_name: str, **kwargs: Any
    ) -> InstallationContext:
        """Set up the installation context for a single app.

        Args:
            app_name: Name of application to install
            **kwargs: Installation options

        Returns:
            Installation context with app configuration and release data

        Raises:
            InstallationError: If setup fails

        """
        logger.info("🚀 Installing from catalog: %s", app_name)

        # Get app configuration from catalog
        app_config = self.catalog_manager.get_app_config(app_name)
        logger.debug("App config for %s: %s", app_name, app_config)
        if not app_config:
            raise InstallationError(f"App configuration not found: {app_name}")

        # Get release configuration
        release_config = self._get_release_config(app_config)
        logger.debug("Release config: %s", release_config)

        # Fetch release data from GitHub
        logger.info("📡 Fetching release data for %s", app_name)
        release_data = await self._fetch_release_data(release_config)
        logger.debug("Release data: %s", release_data)

        # Find AppImage asset using characteristic_suffix from catalog config
        characteristic_suffix = app_config.get("appimage", {}).get("characteristic_suffix", [])

        # Create a GitHubReleaseFetcher to use its select_best_appimage method
        from ..github_client import GitHubReleaseFetcher

        owner = release_config.get("owner")
        repo = release_config.get("repo")

        if not isinstance(owner, str) or not isinstance(repo, str):
            raise InstallationError(f"Invalid owner/repo in release config for {app_name}")

        # Get shared API task from github_client for progress tracking
        shared_api_task_id = getattr(self.github_client, "shared_api_task_id", None)
        fetcher = GitHubReleaseFetcher(owner, repo, self.session, shared_api_task_id)

        appimage_asset = fetcher.select_best_appimage(
            cast(GitHubReleaseDetails, release_data), characteristic_suffix
        )
        if not appimage_asset:
            raise InstallationError(
                f"No AppImage found for {app_name} with "
                f"characteristic_suffix: {characteristic_suffix}"
            )

        # Setup paths
        download_dir = kwargs.get("download_dir", Path.cwd())
        filename = self.download_service.get_filename_from_url(
            appimage_asset["browser_download_url"]
        )
        download_path = download_dir / filename

        # Create combined post-processing task if progress is enabled
        post_processing_task_id = None
        if (
            kwargs.get("show_progress", False)
            and hasattr(self.download_service, "progress_service")
            and self.download_service.progress_service
            and self.download_service.progress_service.is_active()
        ):
            post_processing_task_id = (
                await self.download_service.progress_service.create_post_processing_task(
                    app_name
                )
            )

        return InstallationContext(
            app_name=app_name,
            app_config=app_config,
            release_data=release_data,
            appimage_asset=appimage_asset,
            download_path=download_path,
            post_processing_task_id=post_processing_task_id,
        )

    async def _download_and_verify_appimage(
        self, context: InstallationContext, **kwargs: Any
    ) -> tuple[Path, dict[str, Any] | None]:
        """Download and verify AppImage.

        Args:
            context: Installation context
            **kwargs: Installation options

        Returns:
            Tuple of (Path to downloaded AppImage, verification result)

        Raises:
            InstallationError: If download or verification fails

        """
        # Download AppImage
        appimage_path = await self.download_service.download_appimage(
            context.appimage_asset,
            context.download_path,
            show_progress=kwargs.get("show_progress", True),
        )

        # Verify download if requested (20% of post-processing)
        verification_result = None
        if kwargs.get("verify_downloads", True):
            await self.progress_tracker.update_progress(
                context.post_processing_task_id,
                CatalogProgressSteps.VERIFICATION_START,
                f"🔍 Verifying {context.app_name}...",
            )

            verification_result = await self._perform_verification(
                context,
                post_processing_task_id=context.post_processing_task_id,
                **kwargs,
            )

            await self.progress_tracker.update_progress(
                context.post_processing_task_id,
                CatalogProgressSteps.VERIFICATION_COMPLETE,
                f"✅ {context.app_name} verification",
            )

        return appimage_path, verification_result

    async def _process_appimage_installation(
        self, context: InstallationContext, appimage_path: Path, **_kwargs: Any
    ) -> Path:
        """Process AppImage installation (move, rename, make executable).

        Args:
            context: Installation context
            appimage_path: Path to downloaded AppImage
            **kwargs: Installation options

        Returns:
            Final path of installed AppImage

        """
        # Move to install directory and make executable
        await self.progress_tracker.update_progress(
            context.post_processing_task_id,
            CatalogProgressSteps.MOVE_TO_INSTALL,
            f"📁 Moving {context.app_name} to install directory...",
        )

        final_path = self.storage_service.move_to_install_dir(appimage_path)
        self.storage_service.make_executable(final_path)

        # Handle renaming based on catalog config
        if rename_config := context.app_config.get("appimage", {}).get("rename"):
            clean_name = self.storage_service.get_clean_appimage_name(rename_config)
            final_path = self.storage_service.rename_appimage(final_path, clean_name)

        return final_path

    async def _setup_application_assets(
        self, context: InstallationContext, final_path: Path, **kwargs: Any
    ) -> tuple[Path | None, dict[str, Any]]:
        """Set up application assets (icon, config).

        Args:
            context: Installation context
            final_path: Final path of installed AppImage
            **kwargs: Installation options

        Returns:
            Tuple of (icon path, updated icon config)

        """
        # Extract icon (30% of post-processing)
        icon_path = None
        updated_icon_config: dict[str, Any] = {}
        if context.app_config.get("icon") or True:  # Always try extraction
            await self.progress_tracker.update_progress(
                context.post_processing_task_id,
                CatalogProgressSteps.ICON_START,
                f"🎨 Extracting {context.app_name} icon...",
            )

            icon_path, updated_icon_config = await self._setup_catalog_icon(
                context,
                final_path,
                **kwargs,
            )

            await self.progress_tracker.update_progress(
                context.post_processing_task_id,
                CatalogProgressSteps.ICON_COMPLETE,
                f"✅ {context.app_name} icon extraction",
            )

        return icon_path, updated_icon_config

    async def _create_application_config(
        self,
        context: InstallationContext,
        final_path: Path,
        verification_result: dict[str, Any] | None,
        updated_icon_config: dict[str, Any],
    ) -> None:
        """Create application configuration.

        Args:
            context: Installation context
            final_path: Final path of installed AppImage
            verification_result: Verification results
            updated_icon_config: Updated icon configuration

        """
        # Get icon directory from global config
        icon_dir = self._get_icon_directory()

        # Create app configuration
        await self.progress_tracker.update_progress(
            context.post_processing_task_id,
            CatalogProgressSteps.CONFIG_CREATE,
            f"📁 Creating configuration for {context.app_name}...",
        )

        self._create_app_config(
            AppConfigData(
                app_name=context.app_name,
                app_path=final_path,
                catalog_config=context.app_config,
                release_data=context.release_data,
                icon_dir=icon_dir,
                appimage_asset=context.appimage_asset,
                verification_result=verification_result,
                updated_icon_config=updated_icon_config,
            )
        )

    async def _create_desktop_integration(
        self, context: InstallationContext, final_path: Path, icon_path: Path | None
    ) -> None:
        """Create desktop entry for the application.

        Args:
            context: Installation context
            final_path: Final path of installed AppImage
            icon_path: Path to application icon

        """
        await self.progress_tracker.update_progress(
            context.post_processing_task_id,
            CatalogProgressSteps.DESKTOP_ENTRY,
            f"📁 Creating desktop entry for {context.app_name}...",
        )

        try:
            from ..config import ConfigManager
            from ..desktop import create_desktop_entry_for_app

            config_manager = ConfigManager()
            create_desktop_entry_for_app(
                app_name=context.app_name,
                appimage_path=final_path,
                icon_path=icon_path,
                comment=f"{context.app_name.title()} AppImage Application",
                categories=["Utility"],
                config_manager=config_manager,
            )
            # Desktop entry creation/update logging is handled by the desktop module
        except Exception as e:
            logger.warning("⚠️  Failed to update desktop entry: %s", e)

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
                # Check for existing installation first
                existing_path = await self._handle_existing_installation(app_name, **kwargs)
                if existing_path:
                    return self._build_existing_installation_result(app_name, existing_path)

                # Set up installation context
                context = await self._setup_installation_context(app_name, **kwargs)

                # Download and verify AppImage
                appimage_path, verification_result = await self._download_and_verify_appimage(
                    context, **kwargs
                )

                # Process installation (move, rename, make executable)
                final_path = await self._process_appimage_installation(
                    context, appimage_path, **kwargs
                )

                # Set up application assets (icon)
                icon_path, updated_icon_config = await self._setup_application_assets(
                    context, final_path, **kwargs
                )

                # Create application configuration
                await self._create_application_config(
                    context, final_path, verification_result, updated_icon_config
                )

                # Create desktop integration
                await self._create_desktop_integration(context, final_path, icon_path)

                # Finish progress tracking
                await self.progress_tracker.finish_progress(
                    context.post_processing_task_id,
                    success=True,
                    final_description=f"✅ {app_name}",
                )

                logger.info("✅ Successfully installed from catalog: %s", final_path)
                return self._build_success_result(context, final_path, icon_path)

            except Exception as e:
                await self._handle_installation_error(app_name, e, **kwargs)
                return self._build_error_result(app_name, str(e))

    def _build_existing_installation_result(
        self, app_name: str, existing_path: Path
    ) -> dict[str, Any]:
        """Build result dict for existing installation.

        Args:
            app_name: Application name
            existing_path: Path to existing installation

        Returns:
            Result dictionary for existing installation

        """
        return {
            "target": app_name,
            "success": True,
            "path": str(existing_path),
            "name": existing_path.name,
            "source": "catalog",
            "status": "already_installed",
        }

    def _build_success_result(
        self, context: InstallationContext, final_path: Path, icon_path: Path | None
    ) -> dict[str, Any]:
        """Build result dict for successful installation.

        Args:
            context: Installation context
            final_path: Final path of installed application
            icon_path: Path to application icon

        Returns:
            Result dictionary for successful installation

        """
        return {
            "target": context.app_name,
            "success": True,
            "path": str(final_path),
            "name": final_path.name,
            "source": "catalog",
            "version": extract_and_validate_version(context.release_data.get("tag_name", "")),
            "icon_path": str(icon_path) if icon_path else None,
        }

    def _build_error_result(self, app_name: str, error_message: str) -> dict[str, Any]:
        """Build result dict for failed installation.

        Args:
            app_name: Application name
            error_message: Error message

        Returns:
            Result dictionary for failed installation

        """
        return {
            "target": app_name,
            "success": False,
            "error": error_message,
            "path": None,
        }

    async def _handle_installation_error(
        self, app_name: str, error: Exception, **kwargs: Any
    ) -> None:
        """Handle installation errors with proper logging and progress cleanup.

        Args:
            app_name: Application name
            error: Exception that occurred
            **kwargs: Installation options

        """
        # Mark post-processing as failed if we have a progress task
        post_processing_task_id = kwargs.get("post_processing_task_id")
        if (
            post_processing_task_id
            and hasattr(self.download_service, "progress_service")
            and self.download_service.progress_service
        ):
            await self.progress_tracker.finish_progress(
                post_processing_task_id,
                success=False,
                final_description=f"❌ {app_name} post-processing failed",
            )

        logger.error("❌ Failed to install %s: %s", app_name, error)
        import traceback

        logger.debug("Full traceback: %s", traceback.format_exc())

    async def _handle_existing_installation(
        self, app_name: str, **_kwargs: Any
    ) -> Path | None:
        """Handle existing installation if present.

        Args:
            app_name: Application name
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

    def _get_repository_info(self, context: InstallationContext) -> tuple[str, str]:
        """Extract repository owner and name from context.

        Args:
            context: Installation context

        Returns:
            Tuple of (owner, repo)

        """
        return context.owner, context.repo

    async def _fetch_release_data(self, release_config: dict[str, Any]) -> Any:
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
            raise InstallationError(f"Failed to fetch release data: {e}") from e

    async def _perform_verification(
        self,
        context: InstallationContext,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """Perform download verification based on catalog configuration.

        Args:
            context: Installation context containing all needed data
            **kwargs: Additional keyword arguments

        Returns:
            Dictionary containing successful verification methods and updated config

        Raises:
            InstallationError: If verification fails

        """
        # Get original tag name from release data
        original_tag_name = context.release_data.get(
            "original_tag_name", context.release_data.get("tag_name", "")
        )

        # Use the post-processing task ID from context
        progress_task_id = context.post_processing_task_id

        try:
            result = await self.verification_service.verify_file(
                file_path=context.download_path,
                asset=dict(context.appimage_asset),
                config=context.verification_config,
                owner=context.owner,
                repo=context.repo,
                tag_name=original_tag_name,
                app_name=context.download_path.name,
                assets=context.release_data.get("assets", []),
                progress_task_id=progress_task_id,
            )

            return {
                "successful_methods": result.methods,
                "updated_config": result.updated_config,
            }
        except Exception as e:
            raise InstallationError(str(e)) from e

    async def _setup_catalog_icon(
        self,
        context: InstallationContext,
        appimage_path: Path,
        **_kwargs: Any,
    ) -> tuple[Path | None, dict[str, Any]]:
        """Set up icon from catalog configuration using shared IconService.

        Args:
            context: Installation context containing all needed data
            appimage_path: Path to AppImage for icon extraction
            **kwargs: Additional keyword arguments

        Returns:
            Tuple of (Path to acquired icon or None, updated icon config)

        """
        icon_config_dict = context.app_config.get("icon", {})

        # Check if extraction is enabled (default True)
        extraction_enabled = icon_config_dict.get("extraction", True)
        icon_url = icon_config_dict.get("url", "")

        # Generate filename if not provided
        icon_filename = icon_config_dict.get("name")
        if not icon_filename:
            # Generate filename based on app name and URL
            if icon_url:
                # Try to extract extension from URL
                from urllib.parse import urlparse

                parsed_url = urlparse(icon_url)
                url_path = Path(parsed_url.path)
                icon_extension = url_path.suffix or ".png"
            else:
                icon_extension = ".png"
            icon_filename = f"{context.app_name}{icon_extension}"

        # Create icon configuration
        icon_config = IconConfig(
            extraction_enabled=extraction_enabled,
            icon_url=icon_url if icon_url else None,
            icon_filename=icon_filename,
            preserve_url_on_extraction=False,  # Clear URL on extraction for catalog
        )

        # Get icon directory
        icon_dir = self._get_icon_directory()

        # Use the post-processing task ID from context
        progress_task_id = context.post_processing_task_id

        # Use shared service to acquire icon
        result = await self.icon_service.acquire_icon(
            icon_config=icon_config,
            app_name=context.app_name,
            icon_dir=icon_dir,
            appimage_path=appimage_path,
            current_config=icon_config_dict,
            progress_task_id=progress_task_id,
        )

        return result.icon_path, result.config

    def _create_app_config(self, config_data: AppConfigData) -> None:
        """Create application configuration after successful installation.

        Args:
            config_data: Configuration data containing all necessary information

        """
        # Extract appimage config from catalog config
        appimage_config = config_data.catalog_config.get("appimage", {})

        config = {
            "config_version": "1.0.0",
            "source": "catalog",
            "owner": config_data.catalog_config.get("owner", ""),
            "repo": config_data.catalog_config.get("repo", ""),
            "appimage": {
                "rename": appimage_config.get("rename", config_data.app_name),
                "name_template": appimage_config.get("name_template", ""),
                "characteristic_suffix": appimage_config.get("characteristic_suffix", []),
                "version": extract_and_validate_version(
                    config_data.release_data.get("tag_name", "")
                )
                or "unknown",
                "name": config_data.app_path.name,
                "installed_date": self._get_current_timestamp(),
                "digest": (
                    config_data.appimage_asset.get("digest", "")
                    if config_data.appimage_asset
                    else ""
                ),
            },
            "github": config_data.catalog_config.get(
                "github", {"repo": True, "prerelease": False}
            ),
            "verification": self._get_updated_verification_config(
                config_data.catalog_config, config_data.verification_result
            ),
            "icon": (
                config_data.updated_icon_config or config_data.catalog_config.get("icon", {})
            ),
        }

        # Add icon path if available
        final_icon_config = config_data.updated_icon_config or config_data.catalog_config.get(
            "icon", {}
        )
        if final_icon_config:
            icon_filename = final_icon_config.get("name")
            if icon_filename:
                icon_path = config_data.icon_dir / icon_filename
                if icon_path.exists():
                    config["icon"]["path"] = str(icon_path)

        self.catalog_manager.save_app_config(config_data.app_name, config)

        # Log verification config updates if any
        if config_data.verification_result and config_data.verification_result.get(
            "successful_methods"
        ):
            methods = list(config_data.verification_result["successful_methods"].keys())
            logger.debug(
                f"📝 Saved configuration for {config_data.app_name} with "
                f"updated verification: {', '.join(methods)}"
            )
        else:
            logger.debug("📝 Saved configuration for %s", config_data.app_name)

    def _get_updated_verification_config(
        self, catalog_config: dict[str, Any], verification_result: dict[str, Any] | None
    ) -> Any:
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
                    f"🔧 Updated verification config based on successful methods: "
                    f"{', '.join(methods)}"
                )

        return verification_config

    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string.

        Returns:
            Current timestamp in ISO format

        """
        from datetime import datetime

        return datetime.now().isoformat()
