"""CLI runner for my-unicorn.

Orchestrates the execution of CLI commands by routing parsed
arguments to the appropriate command handlers.
"""

import sys
from argparse import Namespace

from .. import __version__
from ..auth import auth_manager
from ..commands.auth import AuthHandler
from ..commands.backup import BackupHandler
from ..commands.cache import CacheHandler
from ..commands.catalog import CatalogHandler
from ..commands.config import ConfigHandler
from ..commands.install import InstallCommandHandler
from ..commands.migrate import MigrateHandler
from ..commands.remove import RemoveHandler
from ..commands.update import UpdateHandler
from ..commands.upgrade import UpgradeHandler
from ..config import ConfigManager
from ..logger import get_logger
from ..update import UpdateManager
from .parser import CLIParser

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
        self.auth_manager = auth_manager
        self.update_manager = UpdateManager(self.config_manager)

        # Setup file logging
        self._setup_file_logging()

        # Initialize command handlers
        self._init_command_handlers()

    def _setup_file_logging(self) -> None:
        """Set up file logging based on global configuration.

        Enables file logging if specified in the global configuration.
        """
        log_config = self.global_config.get("logging", {})
        if log_config.get("file", {}).get("enabled", False):
            log_file = log_config["file"]["path"]
            log_level = log_config["file"]["level"]
            logger.setup_file_logging(log_file, log_level)

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
            "upgrade": UpgradeHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "catalog": CatalogHandler(
                self.config_manager, self.auth_manager, self.update_manager
            ),
            "list": CatalogHandler(  # Deprecated alias for catalog
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
                print("❌ No command specified. Use --help.")
                sys.exit(1)

            # Route to appropriate command handler
            await self._execute_command(args)

        except KeyboardInterrupt:
            print("\n⏹️  Operation cancelled by user")
            sys.exit(1)
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)

    async def _execute_command(self, args: Namespace) -> None:
        """Execute the specified command with the appropriate handler.

        Args:
            args: Parsed command-line arguments namespace.

        """
        command = args.command

        if command not in self.command_handlers:
            print(f"❌ Unknown command: {command}")
            sys.exit(1)

        # Get command handler and execute
        handler = self.command_handlers[command]

        # Set verbose logging if requested
        if hasattr(args, "verbose") and args.verbose:
            logger.set_console_level_temporarily("DEBUG")

        try:
            await handler.execute(args)
        finally:
            # Restore normal logging level
            if hasattr(args, "verbose") and args.verbose:
                logger.restore_console_level()
