"""Base command handler for my-unicorn CLI commands.

This module provides the abstract base class that all command handlers
inherit from, ensuring consistent interface and shared functionality
across commands.
"""

from abc import ABC, abstractmethod
from argparse import Namespace

from my_unicorn.config import ConfigManager
from my_unicorn.config.schemas.validator import ConfigValidator
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.core.update.update import UpdateManager
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class BaseCommandHandler(ABC):
    """Abstract base class for all command handlers.

    This class provides common functionality and enforces a consistent
    interface for all command implementations.

    Supports dependency injection for all dependencies to enable easier
    testing and explicit dependency management.

    Usage:
        # Create with injected dependencies (preferred for testing):
        config = ConfigManager()
        auth = GitHubAuthManager.create_default()
        update = UpdateManager(config, auth)
        cache = ReleaseCacheManager(config)
        validator = ConfigValidator()

        handler = ConcreteHandler(
            config_manager=config,
            auth_manager=auth,
            update_manager=update,
            cache_manager=cache,
            validator=validator,
        )

        # In production, CLIRunner creates all dependencies and injects them
        # into handlers via _create_handler() factory method.

    Note:
        Concrete handlers must implement the execute() method.
        CLIRunner acts as the composition root, creating and injecting
        all dependencies.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        auth_manager: GitHubAuthManager,
        update_manager: UpdateManager,
        cache_manager: ReleaseCacheManager | None = None,
        validator: ConfigValidator | None = None,
    ) -> None:
        """Initialize the command handler with shared dependencies.

        Args:
            config_manager: Configuration management instance
            auth_manager: GitHub authentication manager
            update_manager: Update management instance
            cache_manager: Optional release cache manager
            validator: Optional config validator

        """
        self.config_manager = config_manager
        self.global_config = config_manager.load_global_config()
        self.auth_manager = auth_manager
        self.update_manager = update_manager
        self.cache_manager = cache_manager
        self.validator = validator

    @abstractmethod
    async def execute(self, args: Namespace) -> None:
        """Execute the command with the given arguments.

        Args:
            args: Parsed command-line arguments

        This method must be implemented by all concrete command handlers.

        """

    def _ensure_directories(self) -> None:
        """Ensure required directories exist based on global config."""
        self.config_manager.ensure_directories_from_config(self.global_config)
