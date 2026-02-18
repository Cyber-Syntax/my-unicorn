"""Install application service for orchestrating installation workflows.

This service follows Clean Architecture principles by separating command
layer concerns from use case orchestration.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config.config import ConfigManager
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import GitHubClient
from my_unicorn.core.install import InstallHandler
from my_unicorn.core.post_download import PostDownloadProcessor
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    github_api_progress_task,
    operation_progress_session,
)
from my_unicorn.logger import get_logger
from my_unicorn.types import InstallPlan

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
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize install application service.

        Args:
            session: HTTP session for downloads
            github_client: GitHub API client
            config_manager: Configuration manager
            install_dir: Installation directory
            progress_reporter: Optional progress reporter for tracking

        """
        self.session = session
        self.github = github_client
        self.config = config_manager
        self.install_dir = install_dir
        self.progress_reporter = progress_reporter or NullProgressReporter()

        # Initialized on demand
        self._download_service: DownloadService | None = None
        self._install_handler: InstallHandler | None = None

    @property
    def download_service(self) -> DownloadService:
        """Get or create download service with progress tracking."""
        if self._download_service is None:
            self._download_service = DownloadService(
                self.session, self.progress_reporter
            )
        return self._download_service

    @property
    def install_handler(self) -> InstallHandler:
        """Get or create install handler."""
        if self._install_handler is None:
            storage_service = FileOperations(self.install_dir)
            post_download_processor = PostDownloadProcessor(
                download_service=self.download_service,
                storage_service=storage_service,
                config_manager=self.config,
                progress_reporter=self.progress_reporter,
            )
            self._install_handler = InstallHandler(
                download_service=self.download_service,
                storage_service=storage_service,
                config_manager=self.config,
                github_client=self.github,
                post_download_processor=post_download_processor,
                progress_reporter=self.progress_reporter,
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
                self.progress_reporter, total_operations=total_operations
            ),
            github_api_progress_task(
                self.progress_reporter,
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


"""Installation state checking for workflow planning.

This module provides functionality to determine which applications
actually need installation work based on their current state.
"""


class InstallStateChecker:
    """Checks which apps need installation work."""

    async def get_apps_needing_installation(
        self,
        config_manager: ConfigManager,
        url_targets: list[str],
        catalog_targets: list[str],
        force: bool,
    ) -> InstallPlan:
        """Check which apps actually need installation work.

        Args:
            config_manager: Configuration manager instance
            url_targets: List of URL targets
            catalog_targets: List of catalog targets
            force: Force installation even if already installed

        Returns:
            InstallPlan with categorized targets

        """
        # All URLs need work by default
        urls_needing_work: list[str] = list(url_targets)
        catalog_needing_work: list[str] = []
        already_installed: list[str] = []

        for app_name in catalog_targets:
            try:
                # Check if app exists in catalog
                try:
                    config_manager.load_catalog(app_name)
                except (FileNotFoundError, ValueError):
                    catalog_needing_work.append(app_name)
                    continue

                if not force:
                    # Check if app is already installed
                    try:
                        installed_config = config_manager.load_app_config(
                            app_name
                        )
                        if installed_config:
                            installed_path = Path(
                                installed_config.get("installed_path", "")
                            )
                            if installed_path.exists():
                                already_installed.append(app_name)
                                continue
                    except (FileNotFoundError, KeyError):
                        # Not installed, needs work
                        pass

                catalog_needing_work.append(app_name)
            except Exception:
                # If we can't determine the status, assume it needs work
                catalog_needing_work.append(app_name)

        return InstallPlan(
            urls_needing_work=urls_needing_work,
            catalog_needing_work=catalog_needing_work,
            already_installed=already_installed,
        )


"""Target resolution for installation workflows.

This module provides functionality to separate mixed installation targets
(URLs and catalog names) into their respective categories.
"""

from my_unicorn.config.config import ConfigManager
from my_unicorn.constants import ERROR_UNKNOWN_APPS_OR_URLS
from my_unicorn.exceptions import InstallationError


class TargetResolver:
    """Resolves installation targets into URLs and catalog names."""

    @staticmethod
    def separate_targets(
        config_manager: ConfigManager, targets: list[str]
    ) -> tuple[list[str], list[str]]:
        """Separate targets into URL and catalog targets.

        This is a helper for CLI code and tests to reuse the same logic
        for categorizing installation targets.

        Args:
            config_manager: Configuration manager instance
            targets: List of mixed targets (URLs or catalog names)

        Returns:
            Tuple of (url_targets, catalog_targets)

        Raises:
            InstallationError: If unknown targets are present

        """
        url_targets: list[str] = []
        catalog_targets: list[str] = []
        unknown_targets: list[str] = []

        available_apps = set(config_manager.list_catalog_apps())

        for target in targets:
            if target.startswith("https://github.com/"):
                url_targets.append(target)
            elif target in available_apps:
                catalog_targets.append(target)
            else:
                unknown_targets.append(target)

        if unknown_targets:
            unknown_list = ", ".join(unknown_targets)
            msg = ERROR_UNKNOWN_APPS_OR_URLS.format(targets=unknown_list)
            raise InstallationError(msg)

        return url_targets, catalog_targets
