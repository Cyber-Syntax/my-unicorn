"""Install command coordinator.

Thin coordinator that validates input and delegates to
InstallApplicationService via ServiceContainer for dependency injection.
"""

from argparse import Namespace

from my_unicorn.cli.container import ServiceContainer
from my_unicorn.core.workflows.services.install_service import InstallOptions
from my_unicorn.ui.display_install import (
    display_no_targets_error,
    print_install_summary,
)
from my_unicorn.ui.progress import ProgressDisplay

from .base import BaseCommandHandler
from .helpers import ensure_app_directories, get_install_paths, parse_targets


class InstallCommandHandler(BaseCommandHandler):
    """Thin coordinator for install command."""

    async def execute(self, args: Namespace) -> None:
        """Execute install command using ServiceContainer for DI."""
        # Parse and validate
        targets = parse_targets(getattr(args, "targets", None))
        if not targets:
            display_no_targets_error()
            return

        # Setup
        ensure_app_directories(self.config_manager, self.global_config)
        _, download_dir = get_install_paths(self.global_config)

        # Create options
        options = InstallOptions(
            concurrent=args.concurrency,
            verify_downloads=not getattr(args, "no_verify", False),
            download_dir=download_dir,
        )

        # Create progress display for CLI
        # Each target has 4 operations: download, verify, icon, install
        total_operations = len(targets) * 4
        progress_display = ProgressDisplay()

        # Use ServiceContainer for dependency injection
        container = ServiceContainer(
            config_manager=self.config_manager,
            progress_reporter=progress_display,
        )

        try:
            async with progress_display.session(total_operations):
                service = container.create_install_application_service()
                results = await service.install(targets, options)
        finally:
            await container.cleanup()

        # Display
        print_install_summary(results)
