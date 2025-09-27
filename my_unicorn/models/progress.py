"""Progress tracking functionality for my-unicorn operations."""

from typing import Any


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
