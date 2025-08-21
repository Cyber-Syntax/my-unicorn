"""Install command for AppImage installations.

This module provides installation from both catalog apps and direct URLs using the Command pattern.
"""

from argparse import Namespace
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.download import DownloadService
from my_unicorn.services.progress import ProgressService
from my_unicorn.storage import StorageService

from ..github_client import GitHubClient
from ..logger import get_logger
from ..strategies.install import ValidationError
from ..strategies.install_catalog import CatalogInstallStrategy
from ..strategies.install_url import URLInstallStrategy
from .base import BaseCommandHandler

logger = get_logger(__name__)


class InstallCommand:
    """Command for installing AppImages from catalog or direct URLs."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        github_client: GitHubClient,
        catalog_manager: Any,
        config_manager: Any,
        install_dir: Path,
        download_dir: Path | None = None,
    ) -> None:
        """Initialize install command with dependencies.

        Args:
            session: aiohttp session for HTTP requests
            github_client: GitHub client for API access
            catalog_manager: Catalog manager for app lookup
            config_manager: Configuration manager for app configs
            install_dir: Directory for installations
            download_dir: Directory for temporary downloads

        """
        self.session = session
        self.github_client = github_client
        self.catalog_manager = catalog_manager
        self.config_manager = config_manager
        self.install_dir = install_dir
        self.download_dir = download_dir or Path.cwd()

        # Progress service will be created when needed
        self.progress_service = None
        self.download_service = None
        self.storage_service = StorageService(install_dir)

        # Strategies will be initialized with progress service
        self.catalog_strategy = None
        self.url_strategy = None

    def _initialize_services_with_progress(self, show_progress: bool) -> None:
        """Initialize services with progress service if needed.

        Args:
            show_progress: Whether to enable progress display

        """
        if self.download_service is None:
            # Create progress service if progress is enabled
            if show_progress:
                self.progress_service = ProgressService()
                self.download_service = DownloadService(self.session, self.progress_service)
            else:
                self.download_service = DownloadService(self.session)

            # Initialize strategies with the configured download service
            self.catalog_strategy = CatalogInstallStrategy(
                catalog_manager=self.catalog_manager,
                config_manager=self.config_manager,
                github_client=self.github_client,
                download_service=self.download_service,
                storage_service=self.storage_service,
                session=self.session,
            )

            self.url_strategy = URLInstallStrategy(
                github_client=self.github_client,
                config_manager=self.config_manager,
                download_service=self.download_service,
                storage_service=self.storage_service,
                session=self.session,
            )

    async def execute(self, targets: list[str], **options: Any) -> list[dict[str, Any]]:
        """Execute installation command.

        Args:
            targets: List of catalog application names or direct URLs
            **options: Installation options including:
                - concurrent: Maximum concurrent installations (default: 3)
                - show_progress: Whether to show progress bars (default: True)
                - verify_downloads: Whether to verify downloads (default: True)
                - force: Force reinstall existing apps (default: False)
                - update: Check for updates (default: False)

        Returns:
            List of installation results

        Raises:
            ValidationError: If targets are invalid

        """
        if not targets:
            raise ValidationError("No installation targets provided")

        logger.info("🚀 Starting installation of %d target(s)", len(targets))

        # Separate targets into URLs and catalog apps
        url_targets, catalog_targets = self._separate_targets(targets)

        # Prepare options with defaults
        install_options = {
            "show_progress": options.get("show_progress", True),
            "verify_downloads": options.get("verify_downloads", True),
            "download_dir": self.download_dir,
            **options,
        }

        # Initialize services with progress configuration
        show_progress = bool(install_options["show_progress"])
        self._initialize_services_with_progress(show_progress)

        # Calculate total operations for progress tracking
        total_operations = len(targets)
        if show_progress and self.progress_service:
            # Each app typically has: download, verify, icon extraction, installation
            total_operations = len(targets) * 4

        # Execute installations with progress session
        if show_progress and self.progress_service:
            async with self.progress_service.session(total_operations):
                results = await self._execute_installations(
                    url_targets, catalog_targets, install_options
                )
        else:
            results = await self._execute_installations(
                url_targets, catalog_targets, install_options
            )

        # Print installation summary
        self._print_installation_summary(results)

        return results

    async def _execute_installations(
        self,
        url_targets: list[str],
        catalog_targets: list[str],
        install_options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute the actual installations.

        Args:
            url_targets: List of URL targets
            catalog_targets: List of catalog targets
            install_options: Installation options

        Returns:
            List of installation results

        """
        results = []

        if url_targets:
            logger.info("📡 Installing %d URL(s)", len(url_targets))
            if self.url_strategy:
                url_results = await self.url_strategy.install(url_targets, **install_options)
            else:
                url_results = []
            results.extend(url_results)

        if catalog_targets:
            logger.info("📚 Installing %d catalog app(s)", len(catalog_targets))
            if self.catalog_strategy:
                catalog_results = await self.catalog_strategy.install(
                    catalog_targets, **install_options
                )
            else:
                catalog_results = []
            results.extend(catalog_results)

        return results

    def _separate_targets(self, targets: list[str]) -> tuple[list[str], list[str]]:
        """Separate targets into URL and catalog targets.

        Args:
            targets: List of mixed targets

        Returns:
            Tuple of (url_targets, catalog_targets)

        Raises:
            ValidationError: If targets are invalid

        """
        url_targets = []
        catalog_targets = []
        unknown_targets = []

        available_apps = self.catalog_manager.get_available_apps()

        for target in targets:
            if target.startswith("https://github.com/"):
                url_targets.append(target)
            elif target in available_apps:
                catalog_targets.append(target)
            else:
                unknown_targets.append(target)

        if unknown_targets:
            unknown_list = ", ".join(unknown_targets)
            raise ValidationError(
                f"Unknown applications or invalid URLs: {unknown_list}. "
                f"Use 'my-unicorn list' to see available apps."
            )

        return url_targets, catalog_targets

    def _print_installation_summary(self, results: list[dict[str, Any]]) -> None:
        """Print installation summary.

        Args:
            results: List of installation results

        """
        if not results:
            logger.info("No installations completed")
            return

        successful = sum(1 for result in results if result.get("success", False))
        total = len(results)

        logger.info("📊 Installation Summary:")
        logger.info("   Successful: %d/%d", successful, total)

        if successful < total:
            failed_apps = [
                result.get("name", "Unknown")
                for result in results
                if not result.get("success", False)
            ]
            logger.warning("   Failed: %s", ", ".join(failed_apps))

        for result in results:
            app_name = result.get("name", "Unknown")
            if result.get("success", False):
                logger.info("   ✅ %s: Installation successful", app_name)
            else:
                error = result.get("error", "Unknown error")
                logger.error("   ❌ %s: %s", app_name, error)


class InstallHandler(BaseCommandHandler):
    """Handler for install command CLI interface."""

    async def execute(self, args: Namespace) -> None:
        """Execute install command.

        Args:
            args: Parsed command line arguments

        """
        try:
            # Extract targets from args
            targets = self._expand_comma_separated_targets(getattr(args, "targets", []))

            if not targets:
                logger.error("❌ No targets specified.")
                logger.info("💡 Use 'my-unicorn list' to see available catalog apps.")
                return

            # Setup directories from config
            self._ensure_directories()
            install_dir = Path(self.global_config["directory"]["storage"])
            download_dir = Path(self.global_config["directory"]["download"])

            # Create session with timeout configuration
            timeout = aiohttp.ClientTimeout(total=1200, sock_read=60, sock_connect=30)
            max_concurrent = self.global_config.get("max_concurrent_downloads", 3)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=max_concurrent)

            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                from ..github_client import GitHubClient

                github_client = GitHubClient(session)

                # Create catalog manager wrapper
                catalog_manager = CatalogManagerAdapter(self.config_manager)

                install_command = InstallCommand(
                    session=session,
                    github_client=github_client,
                    catalog_manager=catalog_manager,
                    config_manager=self.config_manager,
                    install_dir=install_dir,
                    download_dir=download_dir,
                )

                # Convert args to options
                # The concurrency should come from CLI args, which already defaults to global config
                concurrent_value = args.concurrency

                options = {
                    "concurrent": concurrent_value,
                    "show_progress": True,  # Always show progress for install
                    "verify_downloads": not getattr(args, "no_verify", False),
                    "force": False,  # Install doesn't have force option
                    "update": False,  # This is install, not update
                }

                # Log the concurrent value being used for debugging
                logger.info("🔧 Install configuration:")
                logger.info("   Max concurrent installations: %d", concurrent_value)
                logger.info("   Max connections per host: %d", max_concurrent)
                logger.info("   Show progress: %s", options["show_progress"])

                results = await install_command.execute(targets, **options)

                # Check results and log appropriate messages
                if not results:
                    logger.error("No installations were attempted")
                    return

                failed_count = sum(1 for result in results if not result.get("success", False))
                if failed_count > 0:
                    logger.error("%d installation(s) failed", failed_count)
                else:
                    logger.info("All installations completed successfully")

        except ValidationError as e:
            logger.error("Validation error: %s", e)
        except Exception as e:
            logger.error("Installation failed: %s", e)


class CatalogManagerAdapter:
    """Adapter to provide catalog manager interface for the installation system."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize adapter with config manager.

        Args:
            config_manager: ConfigManager instance

        """
        self.config_manager = config_manager

    def get_available_apps(self) -> dict[str, dict[str, Any]]:
        """Get available apps from catalog.

        Returns:
            Dictionary of app names to their configurations

        """
        apps = {}
        for app_name in self.config_manager.list_catalog_apps():
            config = self.config_manager.load_catalog_entry(app_name)
            if config:
                apps[app_name] = config
        return apps

    def get_app_config(self, app_name: str) -> dict[str, Any] | None:
        """Get configuration for a specific app.

        Args:
            app_name: Name of the app

        Returns:
            App configuration or None if not found

        """
        return self.config_manager.load_catalog_entry(app_name)

    def get_installed_app_config(self, app_name: str) -> dict[str, Any] | None:
        """Get installed app configuration.

        Args:
            app_name: Name of the app

        Returns:
            Installed app configuration or None if not found

        """
        try:
            return self.config_manager.load_app_config(app_name)
        except Exception:
            return None

    def save_app_config(self, app_name: str, config: dict[str, Any]) -> None:
        """Save app configuration.

        Args:
            app_name: Name of the app
            config: Configuration to save

        """
        self.config_manager.save_app_config(app_name, config)

    def remove_app_config(self, app_name: str) -> bool:
        """Remove app configuration.

        Args:
            app_name: Name of the app

        Returns:
            True if removed, False if not found

        """
        return self.config_manager.remove_app_config(app_name)
