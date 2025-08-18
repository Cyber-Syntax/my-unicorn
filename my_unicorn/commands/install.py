"""Install command for AppImage installations.

This module provides installation from both catalog apps and direct URLs using the Command pattern.
"""

from argparse import Namespace
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.download import DownloadService
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

        # Initialize services
        self.download_service = DownloadService(session)
        self.storage_service = StorageService(install_dir)

        # Initialize strategies
        self.catalog_strategy = CatalogInstallStrategy(
            catalog_manager=catalog_manager,
            config_manager=config_manager,
            github_client=github_client,
            download_service=self.download_service,
            storage_service=self.storage_service,
            session=session,
        )

        self.url_strategy = URLInstallStrategy(
            github_client=github_client,
            config_manager=config_manager,
            download_service=self.download_service,
            storage_service=self.storage_service,
            session=session,
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

        logger.info(f"🚀 Starting installation of {len(targets)} target(s)")

        # Separate targets into URLs and catalog apps
        url_targets, catalog_targets = self._separate_targets(targets)

        # Prepare options with defaults
        #TODO: use the global setting for the concurrent option
        install_options = {
            "concurrent": options.get("concurrent", 3),
            "show_progress": options.get("show_progress", True),
            "verify_downloads": options.get("verify_downloads", True),
            "download_dir": self.download_dir,
            **options,
        }

        # Execute installations using appropriate strategies
        results = []

        if url_targets:
            logger.info(f"📡 Installing {len(url_targets)} URL(s)")
            url_results = await self.url_strategy.install(url_targets, **install_options)
            results.extend(url_results)

        if catalog_targets:
            logger.info(f"📚 Installing {len(catalog_targets)} catalog app(s)")
            catalog_results = await self.catalog_strategy.install(
                catalog_targets, **install_options
            )
            results.extend(catalog_results)

        # Print installation summary
        self._print_installation_summary(results)

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
            # Try to give helpful error message
            if len(unknown_targets) == 1:
                error_msg = f"Target '{unknown_targets[0]}' is not a valid URL or catalog application name."
            else:
                error_msg = (
                    f"Unknown targets: {', '.join(unknown_targets)}. "
                    f"Targets must be GitHub repository URLs or catalog application names."
                )

            # Add suggestion for catalog apps
            if available_apps:
                app_names = list(available_apps.keys())[:10]  # Show first 10
                suggestion = f" Available catalog apps include: {', '.join(app_names)}"
                if len(available_apps) > 10:
                    suggestion += f" and {len(available_apps) - 10} more."
                error_msg += suggestion

            raise ValidationError(error_msg)

        return url_targets, catalog_targets

    def _print_installation_summary(self, results: list[dict[str, Any]]) -> None:
        """Print summary of installation results.

        Args:
            results: List of installation results

        """
        successful = [r for r in results if r.get("success", False)]
        failed = [r for r in results if not r.get("success", False)]

        logger.info("\n" + "=" * 60)
        logger.info("📋 INSTALLATION SUMMARY")
        logger.info("=" * 60)

        if successful:
            logger.info(f"✅ Successfully installed ({len(successful)}):")
            for result in successful:
                target = result.get("target", "Unknown")
                path = result.get("path", "Unknown")
                source = result.get("source", "unknown")
                version = result.get("version", "")

                status_info = ""
                if result.get("status") == "already_installed":
                    status_info = " (already installed)"
                    print(f"{target} Already installed ")

                version_info = f" v{version}" if version else ""
                source_info = f" [{source}]" if source != "unknown" else ""
                logger.info(f"  • {target}{version_info} → {path}{source_info}{status_info}")

        if failed:
            logger.info(f"\n❌ Failed installations ({len(failed)}):")
            for result in failed:
                target = result.get("target", "Unknown")
                error = result.get("error", "Unknown error")
                logger.info(f"  • {target}: {error}")

        logger.info("=" * 60)

    def validate_targets(self, targets: list[str]) -> None:
        """Validate all targets before installation.

        Args:
            targets: List of URLs or catalog application names

        Raises:
            ValidationError: If any targets are invalid

        """
        try:
            self._separate_targets(targets)
        except ValidationError:
            raise

        logger.debug(f"✅ Validated {len(targets)} target(s)")

    async def cleanup_failed_installations(self, results: list[dict[str, Any]]) -> None:
        """Clean up any failed installations.

        Args:
            results: List of installation results

        """
        failed_results = [r for r in results if not r.get("success", False)]

        for result in failed_results:
            if path := result.get("path"):
                file_path = Path(path)
                if file_path.exists():
                    logger.debug(f"🧹 Cleaning up failed installation: {file_path}")
                    self.storage_service.remove_file(file_path)

    def get_installation_stats(self, results: list[dict[str, Any]]) -> dict[str, int]:
        """Get statistics about installation results.

        Args:
            results: List of installation results

        Returns:
            Dictionary with installation statistics

        """
        stats = {
            "total": len(results),
            "successful": len([r for r in results if r.get("success", False)]),
            "failed": len([r for r in results if not r.get("success", False)]),
            "url_installs": len([r for r in results if r.get("source") == "url"]),
            "catalog_installs": len([r for r in results if r.get("source") == "catalog"]),
            "already_installed": len(
                [r for r in results if r.get("status") == "already_installed"]
            ),
        }

        return stats


class InstallHandler(BaseCommandHandler):
    """Handler for install command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the install command.

        Args:
            args: Command line arguments containing targets and options

        """
        # Extract targets from args
        targets = self._expand_comma_separated_targets(getattr(args, "targets", []))

        if not targets:
            logger.error("❌ No targets specified.")
            logger.info("💡 Use 'list --available' to see available catalog apps.")
            return

        # Get configuration
        from ..config import ConfigManager

        config_manager = ConfigManager()
        config = config_manager._get_default_global_config()

        # Setup directories
        install_dir = Path(config["directory"]["storage"])
        download_dir = Path(config["directory"]["download"])

        # Create session and initialize command
        async with aiohttp.ClientSession() as session:
            github_client = GitHubClient(session)

            # Create catalog manager wrapper
            catalog_manager = CatalogManagerAdapter(config_manager)

            install_command = InstallCommand(
                session=session,
                github_client=github_client,
                catalog_manager=catalog_manager,
                config_manager=config_manager,
                install_dir=install_dir,
                download_dir=download_dir,
            )

            # Convert args to options
            options = {
                "concurrent": getattr(args, "concurrent", 3),
                "show_progress": not getattr(args, "no_progress", False),
                "verify_downloads": not getattr(args, "no_verify", False),
                "force": getattr(args, "force", False),
                "update": getattr(args, "update", False),
            }

            try:
                # Execute installation
                results = await install_command.execute(targets, **options)

                # Handle cleanup for failed installations
                await install_command.cleanup_failed_installations(results)

                # Print final stats
                stats = install_command.get_installation_stats(results)
                if stats["failed"] > 0:
                    logger.error(
                        f"❌ {stats['failed']} installation(s) failed out of {stats['total']}"
                    )
                else:
                    logger.info(
                        f"✅ All {stats['successful']} installation(s) completed successfully!"
                    )

            except ValidationError as e:
                logger.error(f"❌ Validation error: {e}")
                logger.info("💡 Use 'list --available' to see available catalog apps.")
            except Exception as e:
                logger.error(f"❌ Installation failed: {e}")

    def _expand_comma_separated_targets(self, targets: list[str]) -> list[str]:
        """Expand comma-separated targets into individual targets.

        Args:
            targets: List of target strings that may contain commas

        Returns:
            List of individual targets

        """
        expanded = []
        for target in targets:
            # Split by comma and strip whitespace
            parts = [part.strip() for part in target.split(",")]
            expanded.extend(part for part in parts if part)

        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for target in expanded:
            if target not in seen:
                seen.add(target)
                unique_targets.append(target)

        return unique_targets


class CatalogManagerAdapter:
    """Adapter to provide catalog manager interface for the installation system."""

    def __init__(self, config_manager):
        """Initialize adapter with config manager.

        Args:
            config_manager: ConfigManager instance

        """
        self.config_manager = config_manager

    def get_available_apps(self) -> dict[str, dict]:
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

    def get_app_config(self, app_name: str) -> dict | None:
        """Get configuration for a specific app.

        Args:
            app_name: Name of the app

        Returns:
            App configuration or None if not found

        """
        return self.config_manager.load_catalog_entry(app_name)

    def get_installed_app_config(self, app_name: str) -> dict | None:
        """Get installed app configuration.

        Args:
            app_name: Name of the app

        Returns:
            Installed app configuration or None if not found

        """
        try:
            return self.config_manager.load_app_config(app_name)
        except:
            return None

    def save_app_config(self, app_name: str, config: dict) -> None:
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
