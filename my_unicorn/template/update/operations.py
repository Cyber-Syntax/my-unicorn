"""Update operation commands for different types of update actions.

This module implements the Command pattern for different update operations,
allowing the same app selection logic to be combined with different actions.
"""

from abc import ABC, abstractmethod

from ...logger import get_logger
from ...models import UpdateContext
from ...update import UpdateInfo

logger = get_logger(__name__)


class UpdateOperation(ABC):
    """Abstract base class for update operations."""

    @abstractmethod
    async def execute(
        self,
        apps: list[str],
        update_infos: list[UpdateInfo],
        context: UpdateContext,
        session_context: "SessionContext",
    ) -> dict[str, bool]:
        """Execute the operation on the specified apps.

        Args:
            apps: List of app names to process
            update_infos: Update information for the apps
            context: Update context with configuration and dependencies
            session_context: Progress session context

        Returns:
            Dictionary mapping app names to success status

        """


class CheckOnlyOperation(UpdateOperation):
    """Command that only checks for updates without performing them.

    This operation is used when the user wants to see what updates are available
    without actually installing them.
    """

    async def execute(
        self,
        apps: list[str],
        update_infos: list[UpdateInfo],
        context: UpdateContext,
        session_context: "SessionContext",
    ) -> dict[str, bool]:
        """Execute check-only operation.

        This operation doesn't perform any actual updates, it just displays
        the available update information and returns an empty result dict.

        Args:
            apps: List of app names to process
            update_infos: Update information for the apps
            context: Update context with configuration and dependencies
            session_context: Progress session context

        Returns:
            Empty dictionary since no updates are performed

        """
        logger.debug("Executing check-only operation for %d apps", len(apps))

        # Display the check results
        self._display_check_results(update_infos)

        # No actual updates performed
        return {}

    def _display_check_results(self, update_infos: list[UpdateInfo]) -> None:
        """Display the check results in a formatted table.

        Args:
            update_infos: List of UpdateInfo objects to display

        """
        has_updates = False

        for info in update_infos:
            status = "📦 Update available" if info.has_update else "✅ Up to date"
            version_info = (
                f"{info.current_version} -> {info.latest_version}"
                if info.has_update
                else info.current_version
            )

            formatted_version = self._format_version_display(version_info)
            print(f"{info.app_name:<20} {status:<20} {formatted_version}")

            if info.has_update:
                has_updates = True

        if has_updates:
            print("\nRun 'my-unicorn update' to install updates.")

    def _format_version_display(self, version_info: str) -> str:
        """Format version information for display.

        Args:
            version_info: Version information string

        Returns:
            Formatted version string, truncated if too long

        """
        # Truncate long version strings for better display
        if len(version_info) > 40:
            return version_info[:37] + "..."
        return version_info


class UpdateActionOperation(UpdateOperation):
    """Command that performs actual updates on apps.

    This operation performs the actual update process for apps that have
    updates available.
    """

    async def execute(
        self,
        apps: list[str],
        update_infos: list[UpdateInfo],
        context: UpdateContext,
        session_context: "SessionContext",
    ) -> dict[str, bool]:
        """Execute actual update operation.

        This operation filters to apps that need updates and performs the
        actual update process.

        Args:
            apps: List of app names to process
            update_infos: Update information for the apps
            context: Update context with configuration and dependencies
            session_context: Progress session context

        Returns:
            Dictionary mapping app names to success status

        """
        logger.debug("Executing update operation for %d apps", len(apps))

        # Filter to only apps that need updates
        apps_to_update = [info.app_name for info in update_infos if info.has_update]

        if not apps_to_update:
            logger.debug("No apps need updates")
            return {}

        # Show what will be updated
        self._display_update_plan(update_infos)

        # Perform the actual updates using centralized logic
        return await self._execute_updates(apps_to_update, context)

    def _display_update_plan(self, update_infos: list[UpdateInfo]) -> None:
        """Display which apps will be updated.

        Args:
            update_infos: List of UpdateInfo objects

        """
        apps_with_updates = [info for info in update_infos if info.has_update]

        if apps_with_updates:
            print(f"📦 Updating {len(apps_with_updates)} app(s):")
            for info in apps_with_updates:
                print(f"   • {info.app_name}: {info.current_version} → {info.latest_version}")
            print()  # Empty line for better spacing

    async def _execute_updates(
        self, apps_to_update: list[str], context: UpdateContext
    ) -> dict[str, bool]:
        """Execute updates with temporarily suppressed console logging.

        Args:
            apps_to_update: List of app names to update
            context: Update context with dependencies

        Returns:
            Dictionary mapping app names to success status

        """
        from ...logger import get_logger

        logger = get_logger(__name__)

        # Temporarily suppress console logging during downloads
        logger.set_console_level_temporarily("ERROR")

        try:
            return await context.update_manager.update_multiple_apps(apps_to_update)
        finally:
            # Restore normal logging
            logger.restore_console_level()


class DryRunOperation(UpdateOperation):
    """Command that shows what would be updated without doing it.

    This is a future enhancement that could be useful for preview operations.
    """

    async def execute(
        self,
        apps: list[str],
        update_infos: list[UpdateInfo],
        context: UpdateContext,
        session_context: "SessionContext",
    ) -> dict[str, bool]:
        """Execute dry run operation.

        This operation shows what would be updated but doesn't actually
        perform any updates.

        Args:
            apps: List of app names to process
            update_infos: Update information for the apps
            context: Update context with configuration and dependencies
            session_context: Progress session context

        Returns:
            Dictionary mapping app names to simulated success status

        """
        # TODO: Implement when needed
        # This would show what would be updated but not actually do it
        raise NotImplementedError("DryRunOperation not yet implemented")
