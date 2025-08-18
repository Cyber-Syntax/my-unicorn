"""URL-based installation strategy.

This module implements the strategy for installing AppImages from GitHub repository URLs.
"""

import asyncio
from pathlib import Path
from typing import Any

from my_unicorn.download import IconAsset

from ..github_client import (
    GitHubAsset,
    GitHubClient,
    GitHubReleaseDetails,
    GitHubReleaseFetcher,
)
from ..logger import get_logger
from ..verify import Verifier
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

        semaphore = asyncio.Semaphore(self.global_config["max_concurrent_downloads"])

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
                logger.info(f"🚀 Installing from GitHub: {repo_url}")

                # Parse owner/repo from URL
                parts = repo_url.replace("https://github.com/", "").split("/")
                if len(parts) < 2:
                    raise ValueError(f"Invalid GitHub URL format: {repo_url}")

                owner, repo_name = parts[0], parts[1]

                # Use GitHubReleaseFetcher for both fetching and asset selection
                fetcher = GitHubReleaseFetcher(owner, repo_name, self.session)
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
                        download_path, appimage_asset, owner, repo_name
                    )

                # Move to install directory
                final_path = self.storage_service.move_to_install_dir(download_path)

                # Make executable
                self.storage_service.make_executable(final_path)

                # Rename AppImage to clean name based on repo
                clean_name = self.storage_service.get_clean_appimage_name(repo_name.lower())
                final_path = self.storage_service.rename_appimage(final_path, clean_name)

                # Try to download icon
                icon_path = await self._try_download_icon(owner, repo_name, repo_name.lower())

                # Create app configuration
                await self._create_app_config(
                    repo_name.lower(),
                    final_path,
                    owner,
                    repo_name,
                    release_data,
                    appimage_asset,
                    icon_path,
                )

                # Get icon directory from global config
                from ..config import ConfigManager

                config_manager = ConfigManager()

                # Create desktop entry to reflect any changes (icon, paths, etc.)
                try:
                    try:
                        from ..desktop import create_desktop_entry_for_app
                    except ImportError:
                        from ..desktop import create_desktop_entry_for_app

                    desktop_path = create_desktop_entry_for_app(
                        app_name=repo_name.lower(),
                        appimage_path=final_path,
                        icon_path=icon_path,
                        comment=f"{repo_name.title()} AppImage Application",
                        categories=["Utility"],
                        config_manager=config_manager,
                    )
                    # Desktop entry creation/update logging is handled by the desktop module
                except Exception as e:
                    logger.warning(f"⚠️  Failed to update desktop entry: {e}")

                logger.info(f"✅ Successfully installed: {final_path}")

                return {
                    "target": repo_url,
                    "success": True,
                    "path": str(final_path),
                    "name": final_path.name,
                    "source": "url",
                    "version": release_data.get("tag_name"),
                    "icon_path": str(icon_path) if icon_path else None,
                }

            except Exception as e:
                logger.error(f"❌ Failed to install {repo_url}: {e}")
                return {
                    "target": repo_url,
                    "success": False,
                    "error": str(e),
                    "path": None,
                }

    async def _perform_verification(
        self, path: Path, asset: GitHubAsset, owner: str, repo_name: str
    ) -> None:
        """Perform download verification using available methods.

        Args:
            path: Path to downloaded file
            asset: GitHub asset information
            owner: Repository owner
            repo_name: Repository name

        Raises:
            InstallationError: If verification fails

        """
        logger.debug(f"🔍 Starting verification for {path.name}")
        verifier = Verifier(path)
        verification_passed = False

        # Try digest verification first if available
        if asset.get("digest"):
            try:
                logger.debug("🔐 Attempting digest verification")
                verifier.verify_digest(asset["digest"])
                logger.debug("✅ Digest verification passed")
                verification_passed = True
            except Exception as e:
                logger.warning(f"⚠️ Digest verification failed: {e}")

        # Always perform basic file size verification
        try:
            expected_size = asset.get("size", 0)
            if expected_size > 0:
                if not self.download_service.verify_file_size(path, expected_size):
                    if not verification_passed:
                        raise InstallationError("File size verification failed")
                    else:
                        logger.warning("⚠️ File size verification failed, but digest passed")
                else:
                    logger.debug("✅ File size verification passed")
            else:
                logger.debug("⚠️ No expected file size available")
        except Exception as e:
            if not verification_passed:
                raise InstallationError(f"File verification failed: {e}")

        logger.debug("✅ Verification completed")

    async def _try_download_icon(
        self, owner: str, repo_name: str, clean_name: str
    ) -> Path | None:
        """Try to download icon from common locations in the repository.

        Args:
            owner: Repository owner
            repo_name: Repository name
            clean_name: Clean app name for icon filename

        Returns:
            Path to downloaded icon or None

        """
        # Get icon directory from global config
        from ..config import ConfigManager

        config_manager = ConfigManager()
        global_config = config_manager.load_global_config()
        icon_dir = global_config["directory"]["icon"]

        # Common icon paths to try
        icon_paths = [
            "icons/icon.png",
            f"icons/{repo_name}.png",
            "icon.png",
            "logo.png",
            "assets/icon.png",
            "assets/logo.png",
            "resources/icon.png",
            "src/icon.png",
        ]

        for icon_path in icon_paths:
            try:
                icon_url = (
                    f"https://raw.githubusercontent.com/{owner}/{repo_name}/main/{icon_path}"
                )
                icon_filename = f"{clean_name}.png"

                icon_asset: IconAsset = {
                    "icon_filename": icon_filename,
                    "icon_url": icon_url,
                }

                icon_full_path = icon_dir / icon_filename

                # Try to download the icon
                downloaded_path = await self.download_service.download_icon(
                    icon_asset, icon_full_path
                )
                if downloaded_path:
                    logger.debug(f"✅ Downloaded icon from {icon_path}")
                    return downloaded_path

            except Exception as e:
                logger.debug(f"Failed to download icon from {icon_path}: {e}")
                continue

        # Try with master branch as fallback
        for icon_path in icon_paths[:3]:  # Only try the most common ones
            try:
                icon_url = (
                    f"https://raw.githubusercontent.com/{owner}/{repo_name}/master/{icon_path}"
                )
                icon_filename = f"{clean_name}.png"

                icon_asset: IconAsset = {
                    "icon_filename": icon_filename,
                    "icon_url": icon_url,
                }

                icon_full_path = icon_dir / icon_filename

                downloaded_path = await self.download_service.download_icon(
                    icon_asset, icon_full_path
                )
                if downloaded_path:
                    logger.debug(f"✅ Downloaded icon from {icon_path} (master branch)")
                    return downloaded_path

            except Exception as e:
                logger.debug(f"Failed to download icon from {icon_path} (master): {e}")
                continue

        logger.debug(f"⚠️ No icon found for {owner}/{repo_name}")
        return None

    async def _create_app_config(
        self,
        app_name: str,
        app_path: Path,
        owner: str,
        repo_name: str,
        release_data: GitHubReleaseDetails,
        appimage_asset: GitHubAsset,
        icon_path: Path | None,
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
                "version": release_data.get("version", "unknown"),
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
            "icon": {},
        }

        # Add icon information if available
        # We don't store the URL since icon only exists on catalog installs for now.
        # TODO: Implement default icon for URL installs
        if icon_path and icon_path.exists():
            config["icon"]["name"] = icon_path.name
            config["icon"]["url"] = ""
            config["icon"]["path"] = str(icon_path)

        # Save the configuration
        try:
            config_manager.save_app_config(app_name, config)
            logger.debug(f"📝 Saved configuration for {app_name}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save app configuration: {e}")

    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string.

        Returns:
            Current timestamp in ISO format

        """
        from datetime import datetime

        return datetime.now().isoformat()
