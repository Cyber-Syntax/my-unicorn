"""Base strategy interface and data models for update operations.

This module defines the abstract base class for update strategies and the data
models used to pass context and results between strategies and command handlers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..config import ConfigManager
from ..update import UpdateInfo, UpdateManager


@dataclass
class UpdateContext:
    """Context object containing all data needed for update operations.

    This object is passed to strategies and contains all the dependencies
    and configuration needed to perform update operations.
    """

    app_names: list[str] | None
    check_only: bool
    refresh_cache: bool
    config_manager: ConfigManager
    update_manager: UpdateManager


@dataclass
class UpdateResult:
    """Result object containing update operation outcomes.

    This standardized result format is returned by all update strategies
    to provide consistent information about what happened during the operation.
    """

    success: bool
    updated_apps: list[str]
    failed_apps: list[str]
    up_to_date_apps: list[str]
    update_infos: list[UpdateInfo]
    message: str

    @property
    def has_updates(self) -> bool:
        """Check if any apps had updates available."""
        return any(info.has_update for info in self.update_infos)

    @property
    def total_apps(self) -> int:
        """Get total number of apps processed."""
        return len(self.update_infos)


class UpdateStrategy(ABC):
    """Abstract base class for update strategies.

    Each concrete strategy implements a specific update scenario:
    - Check only (no updates performed)
    - Update specific apps
    - Update all installed apps

    This follows the Strategy pattern to encapsulate different algorithms
    for update operations while maintaining a consistent interface.
    """

    @abstractmethod
    async def execute(self, context: UpdateContext) -> UpdateResult:
        """Execute the update strategy.

        Args:
            context: Context object with all required dependencies and data

        Returns:
            UpdateResult containing the outcome of the operation

        """

    @abstractmethod
    def validate_inputs(self, context: UpdateContext) -> bool:
        """Validate strategy-specific inputs.

        Args:
            context: Context object to validate

        Returns:
            True if inputs are valid for this strategy, False otherwise

        """

    def _validate_installed_apps(
        self, app_names: list[str], config_manager: ConfigManager
    ) -> tuple[list[str], list[str]]:
        """Validate that specified apps are installed.

        Args:
            app_names: List of app names to validate
            config_manager: Configuration manager to check installed apps

        Returns:
            Tuple of (valid_apps, invalid_apps)

        """
        installed_apps = config_manager.list_installed_apps()
        valid_apps = []
        invalid_apps = []

        for app in app_names:
            # Case-insensitive matching
            matched = False
            for installed in installed_apps:
                if installed.lower() == app.lower():
                    valid_apps.append(installed)  # Use correct case
                    matched = True
                    break

            if not matched:
                invalid_apps.append(app)

        return valid_apps, invalid_apps

    def _print_invalid_apps(self, invalid_apps: list[str], installed_apps: list[str]) -> None:
        """Print information about invalid app names with suggestions.

        Args:
            invalid_apps: List of invalid app names
            installed_apps: List of all installed apps for suggestions

        """
        if not invalid_apps:
            return

        print("❌ Apps not installed:")
        for app in invalid_apps:
            # Suggest similar installed apps
            suggestions = [inst for inst in installed_apps if app.lower() in inst.lower()][:2]

            if suggestions:
                print(f"   • {app} (did you mean: {', '.join(suggestions)}?)")
            else:
                print(f"   • {app}")

    async def _execute_updates(
        self, context: UpdateContext, app_names: list[str]
    ) -> dict[str, bool]:
        """Execute updates with temporarily suppressed console logging.

        Args:
            context: Update context with dependencies
            app_names: List of app names to update

        Returns:
            Dictionary mapping app names to success status

        """
        from ..logger import get_logger

        logger = get_logger(__name__)

        # Temporarily suppress console logging during downloads
        logger.set_console_level_temporarily("ERROR")

        try:
            return await context.update_manager.update_multiple_apps(app_names)
        finally:
            # Restore normal logging
            logger.restore_console_level()

    def _categorize_update_results(
        self, results: dict[str, bool]
    ) -> tuple[list[str], list[str]]:
        """Categorize update results into successful and failed apps.

        Args:
            results: Dictionary mapping app names to success status

        Returns:
            Tuple of (updated_apps, failed_apps)

        """
        updated_apps: list[str] = []
        failed_apps: list[str] = []

        for app_name, success in results.items():
            if success:
                updated_apps.append(app_name)
            else:
                failed_apps.append(app_name)

        return updated_apps, failed_apps

    async def _execute_with_api_progress(
        self, context: UpdateContext, operation_name: str, total_requests: int, operation_func
    ):
        """Execute an operation with API progress tracking.

        Args:
            context: Update context with dependencies
            operation_name: Name for the operation (e.g., "API assets")
            total_requests: Estimated total API requests
            operation_func: Async function to execute within progress context

        Returns:
            Result of the operation_func

        """
        from ..services.progress import get_progress_service, progress_session

        async with progress_session():
            progress_service = get_progress_service()

            # Create shared API progress task
            api_task_id = await progress_service.create_api_fetching_task(
                endpoint=operation_name, total_requests=total_requests
            )

            # Set shared task for update manager
            context.update_manager._shared_api_task_id = api_task_id

            try:
                result = await operation_func()
                await progress_service.finish_task(api_task_id, success=True)
                return result
            except Exception:
                await progress_service.finish_task(api_task_id, success=False)
                raise
            finally:
                # Clean up shared task
                context.update_manager._shared_api_task_id = None
