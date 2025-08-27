"""URL-based installation strategy.

This module implements the strategy for installing AppImages from GitHub repository URLs.
"""

import asyncio
from pathlib import Path
from typing import Any

from ..github_client import (
    GitHubAsset,
    GitHubClient,
    GitHubReleaseDetails,
    GitHubReleaseFetcher,
)
from ..icon import IconManager
from ..logger import get_logger
from ..services.verification_service import VerificationService
from ..utils import extract_and_validate_version
from .install import InstallationError, InstallStrategy, ValidationError

logger = get_logger(__name__)


class URLInstallStrategy(InstallStrategy):
    """Strategy for installing AppImages from GitHub repository URLs."""

    def __init__(
        self, github_client: GitHubClient, config_manager: Any, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize URL install strategy.

        Args:
            github_client: GitHub client for API access
            config_manager: Configuration manager for app configs
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
        self.github_client = github_client

    def validate_targets(self, targets: list[str]) -> None:
        """Validate that targets are GitHub repository URLs.

        Args:
            targets: List of GitHub repository URLs

        Raises:
            ValidationError: If any target is not a valid GitHub repository URL

        """
        for target in targets:
            if not target.startswith("https://github.com/"):
                raise ValidationError(
                    f"Invalid URL format: {target}. Only GitHub repository URLs are supported."
                )

    async def install(self, targets: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        """Install applications from GitHub repository URLs.

        Args:
            targets: List of GitHub repository URLs
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
            "📡 URL install strategy using %d concurrent installations", concurrent_limit
        )
        semaphore = asyncio.Semaphore(concurrent_limit)

        tasks = [self._install_single_repo(semaphore, url, **kwargs) for url in targets]

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

    async def _install_single_repo(
        self, semaphore: asyncio.Semaphore, repo_url: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Install from a GitHub repository URL.

        Args:
            semaphore: Semaphore for concurrency control
            repo_url: GitHub repository URL
            **kwargs: Installation options

        Returns:
            Installation result dictionary

        """
        async with semaphore:
            try:
                logger.info("🚀 Installing from GitHub: %s", repo_url)

                # Parse owner/repo from URL
                parts = repo_url.replace("https://github.com/", "").split("/")
                if len(parts) < 2:
                    raise ValueError("Invalid GitHub URL format: %s" % repo_url)

                owner, repo_name = parts[0], parts[1]

                # Use GitHubReleaseFetcher for both fetching and asset selection
                # Get shared API task from github_client for progress tracking
                shared_api_task_id = getattr(self.github_client, "shared_api_task_id", None)
                fetcher = GitHubReleaseFetcher(
                    owner, repo_name, self.session, shared_api_task_id
                )
                release_data = await fetcher.fetch_latest_release()
                if not release_data:
                    raise InstallationError(f"No releases found for {owner}/{repo_name}")

                appimage_asset = fetcher.select_best_appimage(
                    release_data, installation_source="url"
                )
                if not appimage_asset:
                    raise InstallationError(
                        f"No AppImage found in {owner}/{repo_name} releases"
                    )

                # Setup paths
                download_dir = kwargs.get("download_dir", Path.cwd())
                filename = self.download_service.get_filename_from_url(
                    appimage_asset["browser_download_url"]
                )
                download_path = download_dir / filename

                # Download AppImage
                await self.download_service.download_appimage(
                    appimage_asset,
                    download_path,
                    show_progress=kwargs.get("show_progress", True),
                )

                # Verify download if requested
                if kwargs.get("verify_downloads", True):
                    await self._perform_verification(
                        download_path, appimage_asset, release_data, owner, repo_name
                    )

                # Move to install directory
                final_path = self.storage_service.move_to_install_dir(download_path)

                # Make executable
                self.storage_service.make_executable(final_path)

                # Rename AppImage to clean name based on repo
                clean_name = self.storage_service.get_clean_appimage_name(repo_name.lower())
                final_path = self.storage_service.rename_appimage(final_path, clean_name)

                # Extract icon from AppImage
                icon_path = None
                from ..config import ConfigManager

                config_manager = ConfigManager()
                global_config = config_manager.load_global_config()
                icon_dir = global_config["directory"]["icon"]

                # Generate icon filename
                icon_filename = f"{repo_name.lower()}.png"
                icon_dest_path = icon_dir / icon_filename

                # Use IconManager to extract icon from AppImage
                icon_manager = IconManager(self.download_service)
                icon_source = "none"
                try:
                    icon_path = await icon_manager.extract_icon_only(
                        appimage_path=final_path,
                        dest_path=icon_dest_path,
                        app_name=repo_name.lower(),
                    )
                    if icon_path:
                        icon_source = "extraction"
                        logger.info("✅ Icon extracted for %s: %s", repo_name, icon_path)
                    else:
                        logger.info("ℹ️  No icon found in AppImage for %s", repo_name)
                except Exception as e:
                    logger.warning("⚠️  Failed to extract icon for %s: %s", repo_name, e)
                    icon_path = None

                # Create app configuration
                await self._create_app_config(
                    repo_name.lower(),
                    final_path,
                    owner,
                    repo_name,
                    release_data,
                    appimage_asset,
                    icon_path,
                    icon_source,
                )

                # config_manager already initialized above

                # Create desktop entry to reflect any changes (icon, paths, etc.)
                try:
                    try:
                        from ..desktop import create_desktop_entry_for_app
                    except ImportError:
                        from ..desktop import create_desktop_entry_for_app

                    desktop_path = create_desktop_entry_for_app(
                        app_name=repo_name.lower(),
                        appimage_path=final_path,
                        comment=f"{repo_name.title()} AppImage Application",
                        categories=["Utility"],
                        config_manager=config_manager,
                    )
                    # Desktop entry creation/update logging is handled by the desktop module
                except Exception as e:
                    logger.warning("⚠️  Failed to update desktop entry: %s", e)

                logger.info("✅ Successfully installed: %s", final_path)

                return {
                    "target": repo_url,
                    "success": True,
                    "path": str(final_path),
                    "name": final_path.name,
                    "source": "url",
                    "version": extract_and_validate_version(release_data.get("tag_name", "")),
                    "icon_path": str(icon_path) if icon_path else None,
                }

            except Exception as e:
                logger.error("❌ Failed to install %s: %s", repo_url, e)
                return {
                    "target": repo_url,
                    "success": False,
                    "error": str(e),
                    "path": None,
                }

    async def _perform_verification(
        self,
        path: Path,
        asset: GitHubAsset,
        release_data: GitHubReleaseDetails,
        owner: str,
        repo_name: str,
    ) -> None:
        """Perform download verification using VerificationService with optimization.

        Args:
            path: Path to downloaded file
            asset: GitHub asset information
            release_data: Full GitHub release data with all assets
            owner: Repository owner
            repo_name: Repository name

        Raises:
            InstallationError: If verification fails

        """
        logger.debug("🔍 Starting verification for %s", path.name)

        # Use VerificationService for comprehensive verification including optimized checksum files
        progress_service = getattr(self.download_service, "progress_service", None)
        verification_service = VerificationService(self.download_service, progress_service)

        # Convert GitHubReleaseDetails assets to the format expected by verification service
        all_assets = []
        for release_asset in release_data["assets"]:
            all_assets.append(
                {
                    "name": release_asset.get("name", ""),
                    "size": release_asset.get("size", 0),
                    "browser_download_url": release_asset.get("browser_download_url", ""),
                    "digest": release_asset.get("digest", ""),
                }
            )

        # Create verification config
        config = {
            "skip": False,
            "checksum_file": None,  # Let it auto-detect with prioritization
            "checksum_hash_type": "sha256",
            "digest_enabled": bool(asset.get("digest")),
        }

        # Convert asset to expected format
        asset_data = {
            "name": asset.get("name", ""),
            "size": asset.get("size", 0),
            "browser_download_url": asset.get("browser_download_url", ""),
            "digest": asset.get("digest", ""),
            "checksum_hash_type": "sha256",
        }

        # Create progress task for verification if available
        progress_task_id = None
        if progress_service and progress_service.is_active():
            progress_task_id = await progress_service.create_verification_task(repo_name)

        try:
            # Perform comprehensive verification with optimized checksum file prioritization
            result = await verification_service.verify_file(
                file_path=path,
                asset=asset_data,
                config=config,
                owner=owner,
                repo=repo_name,
                tag_name=release_data["version"],
                app_name=repo_name,
                assets=all_assets,
                progress_task_id=progress_task_id,
            )

            if not result.passed:
                raise InstallationError(
                    "File verification failed - no verification methods succeeded"
                )

            # Log verification methods used
            methods_used = list(result.methods.keys())
            logger.debug("✅ Verification passed using methods: %s", ", ".join(methods_used))

            logger.debug("✅ Verification completed")

        except Exception as e:
            logger.error("❌ Verification failed: %s", e)
            raise InstallationError(f"File verification failed: {e}")

    async def _create_app_config(
        self,
        app_name: str,
        app_path: Path,
        owner: str,
        repo_name: str,
        release_data: GitHubReleaseDetails,
        appimage_asset: GitHubAsset,
        icon_path: Path | None,
        icon_source: str = "none",
    ) -> None:
        """Create application configuration for URL-based installation.

        Args:
            app_name: Clean application name
            app_path: Path to installed application
            owner: Repository owner
            repo_name: Repository name
            release_data: GitHub release data
            appimage_asset: AppImage asset information
            icon_path: Path to downloaded icon or None
            icon_source: Source of icon (extraction, github, none)

        """
        from ..config import ConfigManager

        config_manager = ConfigManager()

        # Determine stored hash (prefer digest if available)
        stored_hash = ""
        if appimage_asset.get("digest"):
            stored_hash = appimage_asset["digest"]

        config = {
            "config_version": "1.0.0",
            "source": "url",
            "appimage": {
                "version": extract_and_validate_version(release_data.get("version", ""))
                or "unknown",
                "name": app_path.name,
                "rename": app_name,
                "name_template": "",
                "characteristic_suffix": [],
                "installed_date": self._get_current_timestamp(),
                "digest": stored_hash,
            },
            "owner": owner,
            "repo": repo_name,
            "github": {
                "repo": True,
                "prerelease": False,
            },
            "verification": {
                "digest": bool(appimage_asset.get("digest")),
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
            "icon": {
                "extraction": True,
                "source": icon_source,
                "url": "",
            },
        }

        # Add icon information if available (extracted from AppImage)
        if icon_path and icon_path.exists():
            config["icon"]["name"] = icon_path.name
            config["icon"]["installed"] = True
            config["icon"]["path"] = str(icon_path)

        # Save the configuration
        try:
            config_manager.save_app_config(app_name, config)
            logger.debug("📝 Saved configuration for %s", app_name)
        except Exception as e:
            logger.warning("⚠️ Failed to save app configuration: %s", e)

    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string.

        Returns:
            Current timestamp in ISO format

        """
        from datetime import datetime

        return datetime.now().isoformat()
