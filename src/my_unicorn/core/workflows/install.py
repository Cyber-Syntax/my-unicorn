"""Install handler for AppImage installations.

This handler consolidates all installation logic, replacing the complex
template method pattern with a simpler, more maintainable approach.
"""

import asyncio
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.constants import (
    ERROR_NO_APPIMAGE_ASSET,
    ERROR_NO_RELEASE_FOUND,
    InstallSource,
)
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import (
    Asset,
    GitHubClient,
    Release,
    get_github_config,
    parse_github_url,
)
from my_unicorn.core.workflows.post_download import (
    OperationType,
    PostDownloadContext,
    PostDownloadProcessor,
)
from my_unicorn.exceptions import InstallationError
from my_unicorn.logger import get_logger
from my_unicorn.ui.display import ProgressDisplay
from my_unicorn.utils.appimage_utils import select_best_appimage_asset
from my_unicorn.utils.error_formatters import build_install_error_result

logger = get_logger(__name__)


class InstallHandler:
    """Handles installation orchestration.

    Thread Safety:
        - Safe for concurrent access across multiple asyncio tasks
        - Each install operation should use a separate InstallHandler instance
          for isolated progress tracking
        - Download service manages its own progress state
    """

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: FileOperations,
        config_manager: ConfigManager,
        github_client: GitHubClient,
        post_download_processor: PostDownloadProcessor,
        progress_service: ProgressDisplay | None = None,
    ) -> None:
        """Initialize install handler.

        Args:
            download_service: Service for downloading files
            storage_service: Service for storage operations
            config_manager: Configuration manager
            github_client: GitHub API client
            post_download_processor: Processor for post-download operations
            progress_service: Optional progress service for tracking installations

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self.github_client = github_client
        self.progress_service = progress_service
        self.post_download_processor = post_download_processor

    @classmethod
    def create_default(
        cls,
        session: aiohttp.ClientSession,
        config_manager: ConfigManager,
        github_client: GitHubClient,
        install_dir: Path,
        progress_service: ProgressDisplay | None = None,
    ) -> "InstallHandler":
        """Create InstallHandler with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            session: HTTP session for downloads
            config_manager: Configuration manager
            github_client: GitHub client
            install_dir: Installation directory
            progress_service: Optional progress service

        Returns:
            Configured InstallHandler instance

        """
        download_service = DownloadService(session, progress_service)
        storage_service = FileOperations(install_dir)
        post_download_processor = PostDownloadProcessor(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            progress_service=progress_service,
        )

        return cls(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
            post_download_processor=post_download_processor,
            progress_service=progress_service,
        )

    async def install_from_catalog(
        self,
        app_name: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Install app from catalog.

        Args:
            app_name: Name of app in catalog
            **options: Install options (verify_downloads, etc.)

        Returns:
            Installation result dictionary with 'success' key and error details
            if installation failed

        Raises:
            InstallationError: If app configuration is invalid or installation
                workflow fails
            ValueError: If no AppImage asset found in release
            aiohttp.ClientError: If GitHub API request fails

        """
        logger.debug("Starting catalog install: app=%s", app_name)

        try:
            # Get app configuration (v2 format from catalog)
            app_config = self.config_manager.load_catalog(app_name)

            # Extract and validate GitHub configuration
            github_config = get_github_config(app_config)
            owner = github_config.owner
            repo = github_config.repo

            characteristic_suffix = (
                app_config.get("appimage", {})
                .get("naming", {})
                .get("architectures", [])
            )

            release = await self._fetch_release(owner, repo)

            # Select best AppImage asset from compatible options
            asset = select_best_appimage_asset(
                release,
                preferred_suffixes=characteristic_suffix,
                installation_source=InstallSource.CATALOG,
            )
            # Asset is guaranteed non-None (raise_on_not_found=True by default)
            if asset is None:
                raise ValueError(ERROR_NO_APPIMAGE_ASSET)

            # Install workflow
            return await self._install_workflow(
                app_name=app_name,
                asset=asset,
                release=release,
                app_config=app_config,  # type: ignore[arg-type]
                source=InstallSource.CATALOG,
                **options,
            )

        except InstallationError as error:
            logger.error("Failed to install %s: %s", app_name, error)
            return build_install_error_result(error, app_name, is_url=False)
        except Exception as error:
            logger.error("Failed to install %s: %s", app_name, error)
            return build_install_error_result(error, app_name, is_url=False)

    async def install_from_url(
        self,
        github_url: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Install app from GitHub URL.

        Args:
            github_url: GitHub repository URL
            **options: Install options

        Returns:
            Installation result dictionary with 'success' key and error details
            if installation failed

        Raises:
            InstallationError: If URL is invalid or installation workflow fails
            ValueError: If no AppImage asset found in release or URL parsing
                fails
            aiohttp.ClientError: If GitHub API request fails

        """
        logger.debug("Starting URL install: url=%s", github_url)

        try:
            # Parse GitHub URL
            url_info = parse_github_url(github_url)
            owner = url_info["owner"]
            repo = url_info["repo"]
            app_name = url_info.get("app_name") or repo
            prerelease = url_info.get("prerelease", False)

            # Validate GitHub identifiers for security
            config = {"source": {"owner": owner, "repo": repo}}
            get_github_config(config)  # Validates identifiers

            logger.debug(
                "Parsed GitHub URL: owner=%s, repo=%s, app_name=%s",
                owner,
                repo,
                app_name,
            )

            # Fetch latest release (already filtered for x86_64 Linux)
            release = await self._fetch_release(owner, repo)

            # Select best AppImage (filters unstable versions for URLs)
            asset = select_best_appimage_asset(
                release, installation_source=InstallSource.URL
            )
            # Asset is guaranteed non-None (raise_on_not_found=True by default)
            if asset is None:
                raise ValueError(ERROR_NO_APPIMAGE_ASSET)

            # Create v2 format app config template for URL installs
            # Note: verification method will auto-detect checksums
            app_config = {
                "config_version": "2.0.0",
                "metadata": {
                    "name": app_name,
                    "display_name": app_name,
                    "description": "",
                },
                "source": {
                    "type": "github",
                    "owner": owner,
                    "repo": repo,
                    "prerelease": prerelease,
                },
                "appimage": {
                    "naming": {
                        "template": "",
                        "target_name": app_name,
                        "architectures": ["amd64", "x86_64"],
                    }
                },
                "verification": {
                    "method": "digest",  # Will auto-detect checksum files
                },
                "icon": {
                    "method": "extraction",
                    "filename": "",
                },
            }

            # Install workflow
            return await self._install_workflow(
                app_name=app_name,
                asset=asset,
                release=release,
                app_config=app_config,
                source=InstallSource.URL,
                **options,
            )

        except Exception as error:
            logger.error(
                "Failed to install from URL %s: %s", github_url, error
            )
            return build_install_error_result(error, github_url, is_url=True)

    async def install_multiple(
        self,
        catalog_apps: list[str],
        url_apps: list[str],
        **options: Any,
    ) -> list[dict[str, Any]]:
        """Install multiple apps with concurrency control.

        Args:
            catalog_apps: List of catalog app names
            url_apps: List of GitHub URLs
            **options: Install options (concurrent, verify_downloads, etc.)

        Returns:
            List of installation results, one per app. Each result contains
            'success' key and error details if installation failed.

        Note:
            This method catches all exceptions to ensure partial success.
            Individual failures are returned as error results rather than
            raising exceptions.

        """
        concurrent = options.get("concurrent", 3)
        semaphore = asyncio.Semaphore(concurrent)

        async def install_one(app_or_url: str, is_url: bool) -> dict[str, Any]:
            """Install a single app with semaphore control."""
            async with semaphore:
                try:
                    if is_url:
                        return await self.install_from_url(
                            app_or_url, **options
                        )
                    return await self.install_from_catalog(
                        app_or_url, **options
                    )
                except InstallationError as error:
                    logger.error(
                        "Installation error for %s: %s", app_or_url, error
                    )
                    return build_install_error_result(
                        error, app_or_url, is_url
                    )
                except Exception as error:
                    logger.error(
                        "Unexpected error installing %s: %s", app_or_url, error
                    )
                    return {
                        "success": False,
                        "target": app_or_url,
                        "name": app_or_url,
                        "error": f"Installation failed: {error}",
                        "source": InstallSource.URL
                        if is_url
                        else InstallSource.CATALOG,
                    }

        # Create tasks
        tasks = []
        for app in catalog_apps:
            tasks.append(install_one(app, is_url=False))
        for url in url_apps:
            tasks.append(install_one(url, is_url=True))

        return await asyncio.gather(*tasks)

    async def _install_workflow(
        self,
        app_name: str,
        asset: Asset,
        release: Release,
        app_config: dict[str, Any],
        source: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Core install workflow shared by catalog and URL installs.

        Args:
            app_name: Name of the application
            asset: GitHub asset to download
            release: Release information
            app_config: App configuration
            source: Install source (InstallSource.CATALOG or InstallSource.URL)
            **options: Install options (verify_downloads, download_dir)

        Returns:
            Installation result dictionary with verification, icon, config,
            and desktop entry results

        Raises:
            InstallationError: If verification fails or installation step fails
            OSError: If file operations fail (permissions, disk space)
            aiohttp.ClientError: If download fails

        """
        # Get options
        verify = options.get("verify_downloads", True)
        download_dir = options.get("download_dir", Path.cwd())

        logger.debug(
            "Install workflow: app=%s, verify=%s, source=%s",
            app_name,
            verify,
            source,
        )

        try:
            # 1. Download
            download_path = download_dir / asset.name
            logger.info("Downloading %s", app_name)
            downloaded_path = await self.download_service.download_appimage(
                asset, download_path
            )

            # 2. Use PostDownloadProcessor for all post-download operations
            # Extract owner/repo from app_config
            github_config = get_github_config(app_config)

            # Create processing context
            context = PostDownloadContext(
                app_name=app_name,
                downloaded_path=downloaded_path,
                asset=asset,
                release=release,
                app_config=app_config,
                catalog_entry=None,
                operation_type=OperationType.INSTALL,
                owner=github_config.owner,
                repo=github_config.repo,
                verify_downloads=verify,
                source=source,
            )

            # Process download
            result = await self.post_download_processor.process(context)

            if not result.success:
                msg = result.error or "Post-download processing failed"
                raise InstallationError(msg)

            # Build result dictionary
            return {
                "success": True,
                "target": app_name,
                "name": app_name,
                "path": str(result.install_path),
                "source": source,
                "version": release.version,
                "verification": result.verification_result,
                "warning": (
                    result.verification_result.get("warning")
                    if result.verification_result
                    else None
                ),
                "icon": result.icon_result,
                "config": result.config_result,
                "desktop": result.desktop_result,
            }

        except Exception as error:
            logger.error(
                "Installation workflow failed for %s: %s", app_name, error
            )
            raise

    async def _fetch_release(self, owner: str, repo: str) -> Release:
        """Fetch release data from GitHub.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name

        Returns:
            Release object with assets

        Raises:
            InstallationError: If no release found for repository
            aiohttp.ClientError: If GitHub API request fails

        """
        try:
            release = await self.github_client.get_latest_release(owner, repo)
            if not release:
                msg = ERROR_NO_RELEASE_FOUND.format(owner=owner, repo=repo)
                raise InstallationError(msg)
            return release
        except Exception as error:
            logger.error(
                "Failed to fetch release for %s/%s: %s", owner, repo, error
            )
            raise
