"""App selection strategies for update operations.

This module implements the Strategy pattern for app selection, allowing different
approaches to selecting which apps to process during update operations.
"""

from abc import ABC, abstractmethod

from ...logger import get_logger
from ...models import UpdateContext

logger = get_logger(__name__)


class AppSelector(ABC):
    """Abstract base class for app selection strategies."""

    @abstractmethod
    def select_apps(self, context: UpdateContext) -> list[str]:
        """Select which apps to work with.

        Args:
            context: Update context with configuration and dependencies

        Returns:
            List of app names to process

        """


class AllAppsSelector(AppSelector):
    """Strategy that selects all installed apps."""

    def select_apps(self, context: UpdateContext) -> list[str]:
        """Select all installed apps.

        Args:
            context: Update context with configuration and dependencies

        Returns:
            List of all installed app names

        """
        installed_apps = context.config_manager.list_installed_apps()
        logger.debug("Selected all %d installed apps", len(installed_apps))
        return installed_apps


class SpecificAppsSelector(AppSelector):
    """Strategy that selects and validates specified apps."""

    def select_apps(self, context: UpdateContext) -> list[str]:
        """Select and validate specified apps.

        Args:
            context: Update context with app names to validate

        Returns:
            List of valid installed app names

        Raises:
            ValueError: If no apps are specified

        """
        if not context.app_names:
            raise ValueError("No apps specified for specific apps selector")

        installed_apps = context.config_manager.list_installed_apps()
        valid_apps, invalid_apps = self._validate_apps(context.app_names, installed_apps)

        if invalid_apps:
            self._print_invalid_apps(invalid_apps, installed_apps)

        logger.debug(
            "Selected %d valid apps out of %d specified",
            len(valid_apps),
            len(context.app_names),
        )
        return valid_apps

    def _validate_apps(
        self, app_names: list[str], installed_apps: list[str]
    ) -> tuple[list[str], list[str]]:
        """Validate that specified apps are installed.

        Args:
            app_names: List of app names to validate
            installed_apps: List of all installed apps

        Returns:
            Tuple of (valid_apps, invalid_apps)

        """
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


class UpdateAvailableAppsSelector(AppSelector):
    """Strategy that selects only apps with available updates.

    This is a future enhancement that could be useful for operations
    like "update only apps that have updates available".
    """

    def select_apps(self, context: UpdateContext) -> list[str]:
        """Select only apps that have updates available.

        Note: This is a placeholder for future implementation.
        Would require checking for updates first to determine selection.

        Args:
            context: Update context with configuration and dependencies

        Returns:
            List of app names that have updates available

        """
        # TODO: Implement when needed
        # This would require a two-phase approach:
        # 1. Check all apps for updates
        # 2. Return only those with updates available
        raise NotImplementedError("UpdateAvailableAppsSelector not yet implemented")
