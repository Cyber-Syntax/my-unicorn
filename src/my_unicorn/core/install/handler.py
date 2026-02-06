"""Install handler for AppImage installations.

This handler orchestrates all installation logic, delegating to specialized
workflow modules for catalog, URL, and core workflow operations.
"""

import asyncio
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.constants import InstallSource
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import GitHubClient
from my_unicorn.core.post_download import PostDownloadProcessor
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.exceptions import (
    InstallationError,
    InstallError,
    VerificationError,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils.error_formatters import build_install_error_result

from .catalog import install_from_catalog
from .url import install_from_url
from .workflows import fetch_release, install_workflow

logger = get_logger(__name__)


class InstallHandler:
    """Handles AppImage installation orchestration from catalog or URL sources.

    This handler consolidates all installation logic including downloading,
    verification, icon extraction, desktop entry creation, and configuration
    management. It delegates to specialized modules for catalog, URL, and
    workflow operations.

    Attributes:
        download_service: Service for downloading AppImage files.
        storage_service: Service for file storage operations.
        config_manager: Configuration manager for app settings.
        github_client: GitHub API client for release fetching.
        progress_reporter: Progress reporter for tracking installation steps.
        post_download_processor: Processor for post-download workflow.

    Thread Safety:
        - Safe for concurrent access across multiple asyncio tasks
        - Each install operation should use a separate InstallHandler instance
          for isolated progress tracking
        - Download service manages its own progress state

    Example:
        >>> from my_unicorn.cli.container import ServiceContainer
        >>> container = ServiceContainer(config, progress)
        >>> try:
        ...     handler = container.create_install_handler()
        ...     result = await handler.install_from_catalog("firefox")
        ...     if result["success"]:
        ...         print(f"Installed to {result['path']}")
        ... finally:
        ...     await container.cleanup()

    """

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: FileOperations,
        config_manager: ConfigManager,
        github_client: GitHubClient,
        post_download_processor: PostDownloadProcessor,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize install handler.

        Args:
            download_service: Service for downloading files
            storage_service: Service for storage operations
            config_manager: Configuration manager
            github_client: GitHub API client
            post_download_processor: Processor for post-download operations
            progress_reporter: Optional reporter for tracking installations

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self.github_client = github_client
        self.progress_reporter = progress_reporter or NullProgressReporter()
        self.post_download_processor = post_download_processor

    @classmethod
    def create_default(
        cls,
        session: aiohttp.ClientSession,
        config_manager: ConfigManager,
        github_client: GitHubClient,
        install_dir: Path,
        progress_reporter: ProgressReporter | None = None,
    ) -> "InstallHandler":
        """Create InstallHandler with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            session: HTTP session for downloads
            config_manager: Configuration manager
            github_client: GitHub client
            install_dir: Installation directory
            progress_reporter: Optional progress reporter

        Returns:
            Configured InstallHandler instance

        """
        download_service = DownloadService(session, progress_reporter)
        storage_service = FileOperations(install_dir)
        post_download_processor = PostDownloadProcessor(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            progress_reporter=progress_reporter,
        )

        return cls(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
            post_download_processor=post_download_processor,
            progress_reporter=progress_reporter,
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

        """

        return await install_from_catalog(
            app_name=app_name,
            config_manager=self.config_manager,
            download_service=self.download_service,
            post_download_processor=self.post_download_processor,
            fetch_release_fn=self._fetch_release,
            install_workflow_fn=self._install_workflow,
            **options,
        )

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

        """

        return await install_from_url(
            github_url=github_url,
            download_service=self.download_service,
            github_client=self.github_client,
            post_download_processor=self.post_download_processor,
            fetch_release_fn=self._fetch_release,
            install_workflow_fn=self._install_workflow,
            **options,
        )

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
                except (InstallError, VerificationError) as error:
                    logger.error(
                        "Domain error installing %s: %s", app_or_url, error
                    )
                    return build_install_error_result(
                        error, app_or_url, is_url
                    )
                except Exception as error:
                    source = (
                        InstallSource.URL if is_url else InstallSource.CATALOG
                    )
                    install_error = InstallError(
                        str(error),
                        context={"target": app_or_url, "source": source},
                        cause=error,
                    )
                    logger.error(
                        "Unexpected error installing %s: %s",
                        app_or_url,
                        install_error,
                    )
                    return {
                        "success": False,
                        "target": app_or_url,
                        "name": app_or_url,
                        "error": str(install_error),
                        "source": source,
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
        asset: Any,
        release: Any,
        app_config: dict[str, Any],
        source: str,
        download_service: DownloadService | None = None,
        post_download_processor: Any | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        """Core install workflow (delegates to workflows module).

        This method maintains backward compatibility with tests that mock
        internal methods. It delegates to the module-level install_workflow.

        Args:
            app_name: Name of the application
            asset: GitHub asset to download
            release: Release information
            app_config: App configuration
            source: Install source
            download_service: Download service (defaults to self.download_service)
            post_download_processor: Post-download processor (defaults to self.post_download_processor)
            **options: Install options

        Returns:
            Installation result dictionary

        """
        return await install_workflow(
            app_name=app_name,
            asset=asset,
            release=release,
            app_config=app_config,
            source=source,
            download_service=download_service or self.download_service,
            post_download_processor=post_download_processor
            or self.post_download_processor,
            **options,
        )

    async def _fetch_release(self, owner: str, repo: str) -> Any:
        """Fetch release from GitHub (delegates to workflows module).

        This method maintains backward compatibility with tests that mock
        internal methods. It delegates to the module-level fetch_release.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name

        Returns:
            Release object with assets

        """
        return await fetch_release(self.github_client, owner, repo)
