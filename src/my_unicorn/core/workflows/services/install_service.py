"""Install application service for orchestrating installation workflows.

This service follows Clean Architecture principles by separating command
layer concerns from use case orchestration.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import GitHubClient
from my_unicorn.core.workflows.install import InstallHandler
from my_unicorn.core.workflows.install_state_checker import InstallStateChecker
from my_unicorn.core.workflows.target_resolver import TargetResolver
from my_unicorn.logger import get_logger
from my_unicorn.ui.progress import (
    ProgressDisplay,
    github_api_progress_task,
    operation_progress_session,
)

logger = get_logger(__name__)


@dataclass
class InstallOptions:
    """Installation options data class."""

    concurrent: int = 3
    verify_downloads: bool = True
    force: bool = False
    update: bool = False
    download_dir: Path | None = None


class InstallApplicationService:
    """Application service for installing AppImages.

    This service orchestrates the complete installation workflow:
    - Target validation and separation
    - Preflight checks (already installed)
    - Progress management
    - GitHub API coordination
    - Installation execution

    Responsibilities:
    - Use case orchestration (not execution)
    - Progress lifecycle management
    - Service initialization and coordination
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        github_client: GitHubClient,
        config_manager: ConfigManager,
        install_dir: Path,
        progress_service: ProgressDisplay | None = None,
    ) -> None:
        """Initialize install application service.

        Args:
            session: HTTP session for downloads
            github_client: GitHub API client
            config_manager: Configuration manager
            install_dir: Installation directory
            progress_service: Optional progress tracking service

        """
        self.session = session
        self.github = github_client
        self.config = config_manager
        self.install_dir = install_dir
        self.progress = progress_service

        # Initialized on demand
        self._download_service: DownloadService | None = None
        self._install_handler: InstallHandler | None = None

    @property
    def download_service(self) -> DownloadService:
        """Get or create download service with progress tracking."""
        if self._download_service is None:
            self._download_service = DownloadService(
                self.session, self.progress
            )
        return self._download_service

    @property
    def install_handler(self) -> InstallHandler:
        """Get or create install handler."""
        if self._install_handler is None:
            from my_unicorn.core.workflows.post_download import (
                PostDownloadProcessor,
            )

            storage_service = FileOperations(self.install_dir)
            post_download_processor = PostDownloadProcessor(
                download_service=self.download_service,
                storage_service=storage_service,
                config_manager=self.config,
                progress_service=self.progress,
            )
            self._install_handler = InstallHandler(
                download_service=self.download_service,
                storage_service=storage_service,
                config_manager=self.config,
                github_client=self.github,
                post_download_processor=post_download_processor,
                progress_service=self.progress,
            )
        return self._install_handler

    async def install(
        self,
        targets: list[str],
        options: InstallOptions,
    ) -> list[dict[str, Any]]:
        """Execute installation workflow.

        Args:
            targets: List of installation targets (catalog names or URLs)
            options: Installation options

        Returns:
            List of installation results with status and metadata

        """
        logger.info("🚀 Starting installation of %d target(s)", len(targets))

        # Separate targets into URLs and catalog apps
        url_targets, catalog_targets = TargetResolver.separate_targets(
            self.config, targets
        )

        # Build install options dict for handler
        install_opts = {
            "verify_downloads": options.verify_downloads,
            "download_dir": options.download_dir or Path.cwd(),
            "force": options.force,
            "update": options.update,
        }

        # Preflight checks
        checker = InstallStateChecker()
        plan = await checker.get_apps_needing_installation(
            self.config,
            url_targets,
            catalog_targets,
            install_opts.get("force", False),
        )
        urls_needing_work = plan.urls_needing_work
        catalog_needing_work = plan.catalog_needing_work
        already_installed = plan.already_installed

        # Handle all already installed case
        if (
            already_installed
            and not urls_needing_work
            and not catalog_needing_work
        ):
            return self._build_already_installed_results(already_installed)

        # Inform user about already installed apps
        if already_installed:
            self._log_already_installed(already_installed)

        # Execute installations with progress management
        apps_needing_work = len(urls_needing_work) + len(catalog_needing_work)
        # Each app: download, verify, icon extraction, installation
        total_operations = apps_needing_work * 4

        results = []
        async with (
            operation_progress_session(
                self.progress, total_operations=total_operations
            ),
            github_api_progress_task(
                self.progress,
                task_name="GitHub Releases",
                total=apps_needing_work,
            ) as api_task_id,
        ):
            # Set shared API task for GitHub client
            if api_task_id:
                self.github.set_shared_api_task(api_task_id)

            # Execute installations
            results = await self.install_handler.install_multiple(
                catalog_needing_work,
                urls_needing_work,
                **install_opts,
            )

        # Add already installed apps to results
        results.extend(
            self._build_already_installed_results(already_installed)
        )

        return results

    def _build_already_installed_results(
        self, already_installed: list[str]
    ) -> list[dict[str, Any]]:
        """Build results for already installed apps.

        Args:
            already_installed: List of app names already installed

        Returns:
            List of result dictionaries

        """
        return [
            {
                "target": app_name,
                "success": True,
                "path": "already_installed",
                "name": app_name,
                "source": "catalog",
                "status": "already_installed",
            }
            for app_name in already_installed
        ]

    def _log_already_installed(self, already_installed: list[str]) -> None:
        """Log information about already installed apps.

        Args:
            already_installed: List of app names already installed

        """
        logger.info(
            "INFO: Skipping %s already installed app(s):",
            len(already_installed),
        )
        for app_name in already_installed:
            logger.info("   • %s", app_name)
