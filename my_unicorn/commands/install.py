"""Install command for AppImage installations.

This module provides installation from both catalog apps and direct URLs
using a simplified service-based approach.
"""

from argparse import Namespace
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.download import DownloadService
from my_unicorn.file_ops import FileOperations

from ..exceptions import ValidationError
from ..github_client import GitHubClient
from ..logger import get_logger
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

        # Progress and download services will be created when needed
        self.progress_service: Any = None
        self.download_service: Any = None
        self.storage_service = FileOperations(install_dir)
        self.install_service: Any = (
            None  # Will be InstallHandler from services
        )

    def _initialize_services_with_progress(self, show_progress: bool) -> None:
        """Initialize services with progress service if needed.

        Args:
            show_progress: Whether to enable progress display

        """
        if self.download_service is None:
            # Use global progress service if progress is enabled
            if show_progress:
                from ..progress import get_progress_service

                self.progress_service = get_progress_service()
                self.download_service = DownloadService(
                    self.session, self.progress_service
                )
            else:
                self.download_service = DownloadService(self.session)

    async def execute(
        self, targets: list[str], **options: Any
    ) -> list[dict[str, Any]]:
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

        # Check which apps actually need work before starting progress
        (
            urls_needing_work,
            catalog_needing_work,
            already_installed,
        ) = await self._check_apps_needing_work(
            url_targets, catalog_targets, install_options
        )

        # Handle case where all apps are already installed
        if (
            already_installed
            and not urls_needing_work
            and not catalog_needing_work
        ):
            print(
                f"✅ All {len(already_installed)} specified app(s) are already installed:"
            )
            for app_name in already_installed:
                print(f"   • {app_name}")

            # Return success results for already installed apps
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

        # Print info about already installed apps if there are some
        if already_installed:
            print(
                f"ℹ️  Skipping {len(already_installed)} already installed app(s):"
            )
            for app_name in already_installed:
                print(f"   • {app_name}")

        # Calculate operations only for apps that need work
        apps_needing_work = len(urls_needing_work) + len(catalog_needing_work)

        # Execute installations with progress session only if there's work to do
        if show_progress and self.progress_service and apps_needing_work > 0:
            # Each app typically has: download, verify, icon extraction, installation
            total_operations = apps_needing_work * 4
            async with self.progress_service.session(total_operations):
                # Create minimal API progress task - let API calls drive the count
                api_task_id = (
                    await self.progress_service.create_api_fetching_task(
                        endpoint="API assets",
                        total_requests=1,
                    )
                )

                # Set shared API task for GitHub client
                self.github_client.set_shared_api_task(api_task_id)

                try:
                    results = await self._execute_installations(
                        urls_needing_work,
                        catalog_needing_work,
                        install_options,
                    )

                    # Finish API progress task
                    await self.progress_service.finish_task(
                        api_task_id, success=True
                    )
                except Exception:
                    # Finish API progress task with error
                    await self.progress_service.finish_task(
                        api_task_id, success=False
                    )
                    raise
                finally:
                    # Clean up shared task
                    self.github_client.set_shared_api_task(None)
        else:
            results = await self._execute_installations(
                urls_needing_work, catalog_needing_work, install_options
            )

        # Add already installed apps to results
        already_installed_results = [
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
        results.extend(already_installed_results)

        # Print installation summary
        self._print_installation_summary(results)

        return results

    async def _check_apps_needing_work(
        self,
        url_targets: list[str],
        catalog_targets: list[str],
        install_options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        """Check which apps actually need installation work.

        Args:
            url_targets: List of URL targets
            catalog_targets: List of catalog targets
            install_options: Installation options

        Returns:
            Tuple of (urls_needing_work, catalog_needing_work, already_installed)

        """
        urls_needing_work = []
        catalog_needing_work = []
        already_installed = []

        # For URLs, we currently don't have a way to check if they're installed
        # So we assume all URLs need work
        urls_needing_work = url_targets.copy()

        # For catalog apps, check if they're already installed
        for app_name in catalog_targets:
            try:
                # Get app config from catalog
                app_config = self.catalog_manager.get_app_config(app_name)
                if not app_config:
                    catalog_needing_work.append(app_name)
                    continue

                # Check if app is already installed (unless force is specified)
                if not install_options.get("force", False):
                    installed_config = (
                        self.catalog_manager.get_installed_app_config(app_name)
                    )
                    if installed_config:
                        # Check if the installed app file still exists
                        installed_path = Path(
                            installed_config.get("installed_path", "")
                        )
                        if installed_path.exists():
                            already_installed.append(app_name)
                            continue

                # App needs installation
                catalog_needing_work.append(app_name)

            except Exception as e:
                logger.debug(
                    "Error checking installation status for %s: %s",
                    app_name,
                    e,
                )
                # On error, assume it needs installation
                catalog_needing_work.append(app_name)

        return urls_needing_work, catalog_needing_work, already_installed

    async def _execute_installations(
        self,
        url_targets: list[str],
        catalog_targets: list[str],
        install_options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute the actual installations using the install service.

        Args:
            url_targets: List of URL targets
            catalog_targets: List of catalog targets
            install_options: Installation options

        Returns:
            List of installation results

        """
        # Create install service if not already created
        if self.install_service is None:
            from my_unicorn.icon import IconHandler
            from my_unicorn.install import InstallHandler

            self.install_service = InstallHandler(
                download_service=self.download_service,
                storage_service=self.storage_service,
                config_manager=self.config_manager,
                github_client=self.github_client,
                catalog_manager=self.catalog_manager,
                icon_service=IconHandler(
                    download_service=self.download_service,
                    progress_service=self.progress_service,
                ),
            )

        # Install apps using the service
        results = await self.install_service.install_multiple(
            catalog_apps=catalog_targets,
            url_apps=url_targets,
            **install_options,
        )

        return results

    def _separate_targets(
        self, targets: list[str]
    ) -> tuple[list[str], list[str]]:
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

    def _print_installation_summary(
        self, results: list[dict[str, Any]]
    ) -> None:
        """Print installation summary.

        Args:
            results: List of installation results

        """
        if not results:
            logger.info("No installations completed")
            return

        # Categorize results
        already_installed = [
            r for r in results if r.get("status") == "already_installed"
        ]
        newly_installed = [
            r
            for r in results
            if r.get("success", False)
            and r.get("status") != "already_installed"
        ]
        failed = [r for r in results if not r.get("success", False)]

        total = len(results)

        # Handle the case where all apps are already installed
        if len(already_installed) == total:
            logger.info(
                "✅ All %d specified app(s) are already installed:", total
            )
            for result in already_installed:
                logger.info("   • %s", result.get("name", "Unknown"))
            return

        # Print summary for mixed results
        logger.info("📊 Installation Summary:")
        if newly_installed:
            logger.info("   Newly installed: %d", len(newly_installed))
        if already_installed:
            logger.info("   Already installed: %d", len(already_installed))
        if failed:
            logger.info("   Failed: %d", len(failed))

        # Print detailed results
        for result in results:
            app_name = result.get("name", "Unknown")
            if result.get("success", False):
                if result.get("status") == "already_installed":
                    logger.info("   ℹ️  %s: Already installed", app_name)
                else:
                    logger.info("   ✅ %s: Installation successful", app_name)
            else:
                error = result.get("error", "Unknown error")
                logger.error("   ❌ %s: %s", app_name, error)


class InstallCommandHandler(BaseCommandHandler):
    """Handler for install command CLI interface."""

    async def execute(self, args: Namespace) -> None:
        """Execute install command.

        Args:
            args: Parsed command line arguments

        """
        try:
            # Extract targets from args
            targets = self._expand_comma_separated_targets(
                getattr(args, "targets", [])
            )

            if not targets:
                logger.error("❌ No targets specified.")
                logger.info(
                    "💡 Use 'my-unicorn list' to see available catalog apps."
                )
                return

            # Setup directories from config
            self._ensure_directories()
            install_dir = Path(self.global_config["directory"]["storage"])
            download_dir = Path(self.global_config["directory"]["download"])

            # Create session with timeout configuration
            timeout = aiohttp.ClientTimeout(
                total=1200, sock_read=60, sock_connect=30
            )
            max_concurrent = self.global_config.get(
                "max_concurrent_downloads", 3
            )
            connector = aiohttp.TCPConnector(
                limit=10, limit_per_host=max_concurrent
            )

            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector
            ) as session:
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
                logger.info(
                    "   Max concurrent installations: %d", concurrent_value
                )
                logger.info("   Max connections per host: %d", max_concurrent)
                logger.info("   Show progress: %s", options["show_progress"])

                results = await install_command.execute(targets, **options)

                # Check results and log appropriate messages
                if not results:
                    logger.error("No installations were attempted")
                    return

                failed_count = sum(
                    1 for result in results if not result.get("success", False)
                )
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
