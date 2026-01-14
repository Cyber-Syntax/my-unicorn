"""Catalog command handler for my-unicorn CLI.

This module handles the catalog browsing functionality including listing
installed AppImages, showing available apps with descriptions, and displaying
detailed information about specific applications.
"""

from argparse import Namespace

from my_unicorn.cli.commands.base import BaseCommandHandler
from my_unicorn.config import ConfigManager
from my_unicorn.infrastructure.auth import GitHubAuthManager
from my_unicorn.workflows.services.catalog_service import CatalogService
from my_unicorn.workflows.update import UpdateManager


class CatalogHandler(BaseCommandHandler):
    """Handler for catalog command operations."""

    def __init__(
        self,
        config_manager: ConfigManager,
        auth_manager: GitHubAuthManager,
        update_manager: UpdateManager,
    ) -> None:
        """Initialize catalog handler with service."""
        super().__init__(config_manager, auth_manager, update_manager)
        self.catalog_service = CatalogService(self.config_manager)

    async def execute(self, args: Namespace) -> None:
        """Execute the catalog command."""
        # Handle --info argument (mutually exclusive)
        if hasattr(args, "info") and args.info:
            self.catalog_service.display_app_info(args.info)
        # Handle --available argument
        elif hasattr(args, "available") and args.available:
            self.catalog_service.display_available_apps()
        # Handle --installed argument or default
        elif hasattr(args, "installed") and args.installed:
            self.catalog_service.display_installed_apps()
        else:
            # Default: show installed apps
            self.catalog_service.display_installed_apps()
