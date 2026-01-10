"""CLI runner for my-unicorn.

Orchestrates the execution of CLI commands by routing parsed
arguments to the appropriate command handlers.
"""

import logging
import sys
from argparse import Namespace

from my_unicorn import __version__
from my_unicorn.cli.commands.auth import AuthHandler
from my_unicorn.cli.commands.backup import BackupHandler
from my_unicorn.cli.commands.cache import CacheHandler
from my_unicorn.cli.commands.catalog import CatalogHandler
from my_unicorn.cli.commands.config import ConfigHandler
from my_unicorn.cli.commands.install import InstallCommandHandler
from my_unicorn.cli.commands.migrate import MigrateHandler
from my_unicorn.cli.commands.remove import RemoveHandler
from my_unicorn.cli.commands.token import TokenHandler
from my_unicorn.cli.commands.update import UpdateHandler
from my_unicorn.cli.commands.upgrade import UpgradeHandler
from my_unicorn.cli.parser import CLIParser
from my_unicorn.config import ConfigManager
from my_unicorn.infrastructure.auth import GitHubAuthManager
from my_unicorn.logger import get_logger, update_logger_from_config
from my_unicorn.workflows.update import UpdateManager

logger = get_logger(__name__)


class CLIRunner:
    """CLI command runner and orchestrator."""

    def __init__(self) -> None:
        """Initialize CLI runner with shared dependencies.

        Sets up configuration, authentication, update management,
        logging, and command handlers.
        """
        self.config_manager = ConfigManager()
        self.global_config = self.config_manager.load_global_config()

        # Update logger with config-based log levels
        update_logger_from_config()

        # Create auth manager with default keyring storage
        self.auth_manager = GitHubAuthManager.create_default()

        # Create update manager with injected dependencies
        self.update_manager = UpdateManager(
            self.config_manager, self.auth_manager
        )

        # Initialize command handlers
        self._init_command_handlers()

    def _init_command_handlers(self) -> None:
        """Initialize all command handlers with shared dependencies.

        Prepares command handler instances for each supported CLI
        command.
        """
        self.command_handlers = {
            "install": InstallCommandHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "update": UpdateHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "upgrade": UpgradeHandler(),
            "catalog": CatalogHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "migrate": MigrateHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "remove": RemoveHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "backup": BackupHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "cache": CacheHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "token": TokenHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "auth": AuthHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "config": ConfigHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
        }

    async def run(self) -> None:
        """Run the CLI application.

        Parses arguments, handles global flags, validates commands,
        and routes to the appropriate handler.

        Raises:
            KeyboardInterrupt: If the user cancels the operation.
            Exception: For any unexpected errors during execution.

        """
        try:
            # Parse command-line arguments
            parser = CLIParser(self.global_config)
            args = parser.parse_args()

            # Global: --version should print package version and exit early.
            if getattr(args, "version", False):
                # Use __version__ from package which has proper fallback logic
                print(__version__)
                return

            # Validate command
            if not args.command:
                logger.error("No command specified")
                sys.exit(1)

            # Route to appropriate command handler
            await self._execute_command(args)

        except KeyboardInterrupt:
            logger.info("Operation cancelled by user via KeyboardInterrupt")
            sys.exit(1)
        except Exception:
            logger.exception("Unexpected error")
            sys.exit(1)

    async def _execute_command(self, args: Namespace) -> None:
        """Execute the specified command with the appropriate handler.

        Args:
            args: Parsed command-line arguments namespace.

        """
        command = args.command

        if command not in self.command_handlers:
            logger.error("Unknown command: %s", command)
            sys.exit(1)

        # Get command handler and execute
        handler = self.command_handlers[command]

        # Set verbose logging if requested - find console handler
        console_handler = None
        original_level = None
        if hasattr(args, "verbose") and args.verbose:
            for h in logger.handlers:
                if isinstance(h, logging.StreamHandler) and not isinstance(
                    h, logging.FileHandler
                ):
                    console_handler = h
                    original_level = h.level
                    h.setLevel(logging.DEBUG)
                    break

        try:
            await handler.execute(args)
        finally:
            # Restore normal logging level
            if console_handler and original_level is not None:
                console_handler.setLevel(original_level)
