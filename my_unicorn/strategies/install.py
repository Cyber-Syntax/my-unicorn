"""Abstract strategy interface for installation operations.

This module defines the base strategy interface that all installation
strategies must implement, along with common functionality shared across strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.download import DownloadService
from my_unicorn.storage import StorageService


# Common progress tracking constants
class ProgressSteps:
    """Constants for progress tracking percentages across all installation strategies."""

    INIT = 0.0
    VALIDATION = 10.0
    FETCHING_DATA = 20.0
    DOWNLOADING = 40.0
    VERIFICATION = 60.0
    PROCESSING = 75.0
    FINALIZING = 90.0
    COMPLETED = 100.0


class ProgressTracker:
    """Common progress tracking functionality for installation strategies."""

    def __init__(self, download_service: Any) -> None:
        """Initialize progress tracker.

        Args:
            download_service: Service with progress tracking capability

        """
        self.download_service = download_service
        self.progress_service = getattr(download_service, "progress_service", None)

    async def update_progress(
        self,
        task_id: str | None,
        completed: float,
        description: str,
    ) -> None:
        """Update progress if tracking is enabled.

        Args:
            task_id: Progress task ID
            completed: Completion percentage
            description: Progress description

        """
        if task_id and self.progress_service:
            await self.progress_service.update_task(
                task_id,
                completed=completed,
                description=description,
            )

    async def finish_progress(
        self,
        task_id: str | None,
        success: bool,
        final_description: str,
        final_total: float = ProgressSteps.COMPLETED,
    ) -> None:
        """Finish progress tracking.

        Args:
            task_id: Progress task ID
            success: Whether operation succeeded
            final_description: Final progress description
            final_total: Final completion percentage

        """
        if task_id and self.progress_service:
            await self.progress_service.finish_task(
                task_id,
                success=success,
                final_description=final_description,
                final_total=final_total,
            )


@dataclass(frozen=True, slots=True)
class BaseInstallationContext:
    """Base context for installation operations."""

    app_name: str
    download_path: Path
    post_processing_task_id: str | None = None


class InstallStrategy(ABC):
    """Abstract base class for installation strategies."""

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: StorageService,
        session: aiohttp.ClientSession,
        config_manager: ConfigManager,
    ) -> None:
        """Initialize strategy with required services.

        Args:
            download_service: Service for downloading files
            storage_service: Service for file operations
            session: aiohttp session for HTTP requests
            config_manager: Configuration manager

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.session = session
        self.config_manager = config_manager or ConfigManager()
        self.global_config = self.config_manager.load_global_config()
        self.progress_tracker = ProgressTracker(download_service)

    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string.

        Returns:
            Current timestamp in ISO format

        """
        return datetime.now().isoformat()

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
            ValidationError: If targets are invalid for this strategy

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
