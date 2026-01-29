"""Install command coordinator.

Thin coordinator that validates input and delegates to
InstallApplicationService.
"""

from argparse import Namespace

from my_unicorn.core.github import GitHubClient
from my_unicorn.core.http_session import create_http_session
from my_unicorn.core.workflows.services.install_service import (
    InstallApplicationService,
    InstallOptions,
)
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
        """Execute install command."""
        # Parse and validate
        targets = parse_targets(getattr(args, "targets", None))
        if not targets:
            display_no_targets_error()
            return

        # Setup
        ensure_app_directories(self.config_manager, self.global_config)
        install_dir, download_dir = get_install_paths(self.global_config)

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
                github_client=GitHubClient(
                    session, progress_service=progress_service
                ),
                config_manager=self.config_manager,
                install_dir=install_dir,
                progress_service=progress_service,
            )
            results = await service.install(targets, options)

        # Display
        print_install_summary(results)
