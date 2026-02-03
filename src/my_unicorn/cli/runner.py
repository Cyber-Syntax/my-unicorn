"""CLI runner for my-unicorn.

Orchestrates the execution of CLI commands by routing parsed
arguments to the appropriate command handlers.

Acts as the composition root for dependency injection, creating
all shared dependencies (config, cache, validator) and injecting
them into command handlers.
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
from my_unicorn.config.schemas.validator import ConfigValidator
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.core.workflows.update import UpdateManager
from my_unicorn.logger import get_logger, update_logger_from_config

logger = get_logger(__name__)


class CLIRunner:
    """CLI command runner and orchestrator.

    Acts as the composition root for the application's dependency injection
    pattern. Creates all shared dependencies (ConfigValidator, ConfigManager,
    ReleaseCacheManager, GitHubAuthManager, UpdateManager) and injects them
    into command handlers.

    Usage:
        # Standard usage (creates all dependencies internally):
        runner = CLIRunner()
        await runner.run()

        # Dependencies created in __init__:
        # 1. ConfigValidator() - no dependencies
        # 2. ConfigManager(validator=validator)
        # 3. ReleaseCacheManager(config_manager, ttl_hours=24)
        # 4. GitHubAuthManager.create_default()
        # 5. UpdateManager(config_manager, auth_manager)

        # All handlers receive the same instances via _create_handler()

    Note:
        This class implements the composition root pattern. All dependency
        creation happens here, making the dependency graph explicit and
        testable. Handlers receive pre-configured instances rather than
        creating their own or accessing global singletons.
    """

    def __init__(self) -> None:
        """Initialize CLI runner with shared dependencies.

        Sets up configuration, authentication, update management,
        logging, and command handlers.

        Acts as the composition root: creates ConfigValidator,
        ConfigManager, ReleaseCacheManager, and other shared
        dependencies, then injects them into command handlers.
        """
        # Create validator first (no dependencies)
        self.validator = ConfigValidator()

        # Create config manager with injected validator
        self.config_manager = ConfigManager(validator=self.validator)
        self.global_config = self.config_manager.load_global_config()

        # Create cache manager with injected config
        self.cache_manager = ReleaseCacheManager(
            self.config_manager, ttl_hours=24
        )

        # Update logger with config-based log levels
        update_logger_from_config()

        # Create auth manager with default keyring storage
        self.auth_manager = GitHubAuthManager.create_default()

        # Create update manager with injected dependencies
        self.update_manager = UpdateManager(
            self.config_manager,
            self.auth_manager,
            self.cache_manager,
        )

        # Initialize command handlers
        self._init_command_handlers()

    def _create_handler(self, handler_class: type) -> object:
        """Create command handler with standard dependencies.

        Args:
            handler_class: The handler class to instantiate.

        Returns:
            Instantiated handler with injected dependencies.
        """
        # UpgradeHandler doesn't need dependencies
        if handler_class is UpgradeHandler:
            return handler_class()

        return handler_class(
            config_manager=self.config_manager,
            auth_manager=self.auth_manager,
            update_manager=self.update_manager,
            cache_manager=self.cache_manager,
            validator=self.validator,
        )

    def _init_command_handlers(self) -> None:
        """Initialize all command handlers with shared dependencies.

        Prepares command handler instances for each supported CLI
        command.
        """
        self.command_handlers = {
            "install": self._create_handler(InstallCommandHandler),
            "update": self._create_handler(UpdateHandler),
            "upgrade": self._create_handler(UpgradeHandler),
            "catalog": self._create_handler(CatalogHandler),
            "migrate": self._create_handler(MigrateHandler),
            "remove": self._create_handler(RemoveHandler),
            "backup": self._create_handler(BackupHandler),
            "cache": self._create_handler(CacheHandler),
            "token": self._create_handler(TokenHandler),
            "auth": self._create_handler(AuthHandler),
            "config": self._create_handler(ConfigHandler),
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
