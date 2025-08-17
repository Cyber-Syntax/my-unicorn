"""Check-only update strategy implementation.

This module implements the strategy for checking updates without performing
any actual updates. It provides detailed information about available updates
for apps without modifying the system.
"""

from ..logger import get_logger
from ..update import UpdateInfo
from .update_strategy import UpdateContext, UpdateResult, UpdateStrategy

logger = get_logger(__name__)


class CheckOnlyUpdateStrategy(UpdateStrategy):
    """Strategy for checking updates without installing them.

    This strategy checks for available updates for specified apps or all
    installed apps, but does not perform any actual updates. It's useful
    for getting status information about available updates.
    """

    def validate_inputs(self, context: UpdateContext) -> bool:
        """Validate inputs for check-only strategy.

        Args:
            context: Update context to validate

        Returns:
            True if inputs are valid, False otherwise

        """
        if context.app_names:
            installed_apps = context.config_manager.list_installed_apps()
            valid_apps, invalid_apps = self._validate_installed_apps(
                context.app_names, context.config_manager
            )

            if invalid_apps:
                self._print_invalid_apps(invalid_apps, installed_apps)

                if not valid_apps:
                    print("\nNo valid apps to check.")
                    return False

            # Update context with only valid apps
            context.app_names = valid_apps

        return True

    async def execute(self, context: UpdateContext) -> UpdateResult:
        """Execute the check-only update strategy.

        Args:
            context: Update context with dependencies and configuration

        Returns:
            UpdateResult with check results

        """
        logger.debug("Executing check-only update strategy")

        # Get update information for specified apps or all apps
        update_infos = await context.update_manager.check_all_updates(context.app_names)

        if not update_infos:
            print("No installed apps found to check.")
            return UpdateResult(
                success=True,
                updated_apps=[],
                failed_apps=[],
                up_to_date_apps=[],
                update_infos=[],
                message="No apps to check",
            )

        # Categorize apps
        apps_with_updates: list[str] = []
        apps_up_to_date: list[str] = []

        for info in update_infos:
            if info.has_update:
                apps_with_updates.append(info.app_name)
            else:
                apps_up_to_date.append(info.app_name)

        # Display results
        self._display_check_results(update_infos)

        # Prepare result message
        total_apps = len(update_infos)
        updates_available = len(apps_with_updates)

        if updates_available > 0:
            message = (
                f"Found {updates_available} update(s) available out of "
                f"{total_apps} app(s) checked"
            )
        else:
            message = f"All {total_apps} app(s) are up to date"

        return UpdateResult(
            success=True,
            updated_apps=[],  # No apps were actually updated
            failed_apps=[],
            up_to_date_apps=apps_up_to_date,
            update_infos=update_infos,
            message=message,
        )

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
