"""Base command handler for my-unicorn CLI commands.

This module provides the abstract base class that all command handlers inherit from,
ensuring consistent interface and shared functionality across commands.
"""

from abc import ABC, abstractmethod
from argparse import Namespace

from ..auth import GitHubAuthManager
from ..config import ConfigManager
from ..logger import get_logger
from ..update import UpdateManager

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

    def _expand_comma_separated_targets(self, targets: list[str]) -> list[str]:
        """Expand comma-separated target strings into a flat list.

        Args:
            targets: List of target strings that may contain comma-separated values

        Returns:
            Flattened list of unique targets with duplicates removed

        """
        all_targets = []
        for target in targets:
            if "," in target:
                all_targets.extend([t.strip() for t in target.split(",") if t.strip()])
            else:
                all_targets.append(target.strip())

        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for target in all_targets:
            target_lower = target.lower()
            if target_lower not in seen:
                seen.add(target_lower)
                unique_targets.append(target)

        return unique_targets
