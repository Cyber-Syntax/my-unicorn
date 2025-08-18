"""Abstract strategy interface for installation operations.

This module defines the base strategy interface that all installation
strategies must implement.
"""

from abc import ABC, abstractmethod
from typing import Any

import aiohttp

from my_unicorn.download import DownloadService
from my_unicorn.storage import StorageService


class InstallStrategy(ABC):
    """Abstract base class for installation strategies."""

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: StorageService,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize strategy with required services.

        Args:
            download_service: Service for downloading files
            storage_service: Service for file operations
            session: aiohttp session for HTTP requests

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.session = session

    @abstractmethod
    async def install(self, targets: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        """Install applications using this strategy.

        Args:
            targets: List of installation targets (URLs, app names, etc.)
            **kwargs: Additional strategy-specific options

        Returns:
            List of installation results

        Raises:
            InstallationError: If installation fails

        """

    @abstractmethod
    def validate_targets(self, targets: list[str]) -> None:
        """Validate that targets are appropriate for this strategy.

        Args:
            targets: List of installation targets

        Raises:
            ValueError: If targets are invalid for this strategy

        """


class InstallationError(Exception):
    """Raised when installation fails."""

    def __init__(self, message: str, target: str | None = None) -> None:
        """Initialize installation error.

        Args:
            message: Error message
            target: Target that failed to install

        """
        super().__init__(message)
        self.target = target


class ValidationError(Exception):
    """Raised when target validation fails."""
