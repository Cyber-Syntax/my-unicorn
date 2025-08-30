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
