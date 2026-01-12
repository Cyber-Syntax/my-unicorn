"""Install command coordinator.

Thin coordinator that validates input and delegates to
InstallApplicationService.
"""

from argparse import Namespace
from pathlib import Path

from my_unicorn.infrastructure.github import GitHubClient
from my_unicorn.infrastructure.http_session import create_http_session
from my_unicorn.logger import get_logger
from my_unicorn.ui.display_install import print_install_summary
from my_unicorn.ui.progress import ProgressDisplay
from my_unicorn.workflows.services.install_service import (
    InstallApplicationService,
    InstallOptions,
)

from .base import BaseCommandHandler
from .catalog_adapter import CatalogManagerAdapter

logger = get_logger(__name__)


class InstallCommandHandler(BaseCommandHandler):
    """Thin coordinator for install command."""

    async def execute(self, args: Namespace) -> None:
        """Execute install command."""
        # Parse and validate
        targets = self._expand_comma_separated_targets(
            getattr(args, "targets", [])
        )
        if not targets:
            logger.error("❌ No targets specified.")
            logger.info(
                "💡 Use 'my-unicorn catalog' to see available catalog apps."
            )
            return

        # Setup
        self._ensure_directories()
        install_dir = Path(self.global_config["directory"]["storage"])
        download_dir = Path(self.global_config["directory"]["download"])

        # Create options
        options = InstallOptions(
            concurrent=args.concurrency,
            verify_downloads=not getattr(args, "no_verify", False),
            download_dir=download_dir,
        )

        # Execute via service
        async with create_http_session(self.global_config) as session:
            progress_service = ProgressDisplay()

            service = InstallApplicationService(
                session=session,
                github_client=GitHubClient(session, progress_service),
                catalog_manager=CatalogManagerAdapter(self.config_manager),
                config_manager=self.config_manager,
                install_dir=install_dir,
                progress_service=progress_service,
            )
            results = await service.install(targets, options)

        # Display
        print_install_summary(results)
