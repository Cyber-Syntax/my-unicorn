"""Base command handler for my-unicorn CLI commands.

This module provides the abstract base class that all command handlers inherit from,
ensuring consistent interface and shared functionality across commands.
"""

from abc import ABC, abstractmethod
from argparse import Namespace

from my_unicorn.config import ConfigManager
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.workflows.update import UpdateManager
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class BaseCommandHandler(ABC):
    """Abstract base class for all command handlers.

    This class provides common functionality and enforces a consistent
    interface for all command implementations.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        auth_manager: GitHubAuthManager,
        update_manager: UpdateManager,
    ) -> None:
        """Initialize the command handler with shared dependencies.

        Args:
            config_manager: Configuration management instance
            auth_manager: GitHub authentication manager
            update_manager: Update management instance

        """
        self.config_manager = config_manager
        self.global_config = config_manager.load_global_config()
        self.auth_manager = auth_manager
        self.update_manager = update_manager

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
