"""Update specific apps strategy implementation.

This module implements the strategy for updating only specified apps.
It validates the requested apps, checks for updates, and performs updates
only on the apps that actually need updating.
"""

from ..logger import get_logger
from .update import UpdateContext, UpdateResult, UpdateStrategy

logger = get_logger(__name__)


class UpdateSpecificAppsStrategy(UpdateStrategy):
    """Strategy for updating only specified apps.

    This strategy takes a list of app names, validates they are installed,
    checks which ones need updates, and performs updates only on those
    that actually have updates available.
    """

    def validate_inputs(self, context: UpdateContext) -> bool:
        """Validate inputs for specific apps update strategy.

        Args:
            context: Update context to validate

        Returns:
            True if inputs are valid, False otherwise

        """
        if not context.app_names:
            print("❌ No apps specified for update")
            return False

        if context.check_only:
            logger.warning(
                "check_only flag should not be used with specific apps update strategy"
            )

        installed_apps = context.config_manager.list_installed_apps()
        valid_apps, invalid_apps = self._validate_installed_apps(
            context.app_names, context.config_manager
        )

        if invalid_apps:
            self._print_invalid_apps(invalid_apps, installed_apps)

            if not valid_apps:
                print("\nNo valid apps to update.")
                return False

        # Update context with only valid apps
        context.app_names = valid_apps
        return True

    async def execute(self, context: UpdateContext) -> UpdateResult:
        """Execute the specific apps update strategy.

        Args:
            context: Update context with dependencies and configuration

        Returns:
            UpdateResult with update results

        """
        logger.debug("Executing update strategy for specific apps: %s", context.app_names)

        # At this point, app_names should not be None due to validation
        assert context.app_names is not None, "app_names should not be None after validation"

        app_count = len(context.app_names)
        print(f"🔄 Updating {app_count} app(s): {', '.join(context.app_names)}")

        # Check which apps actually need updates
        print("🔍 Checking for updates...")
        update_infos = await context.update_manager.check_all_updates(context.app_names)

        # Detect if update_infos is empty due to authentication failure or other errors
        if not update_infos:
            message = (
                "❌ Failed to check updates for specified apps. "
                "This may be due to invalid GitHub Personal Access Token (PAT)."
            )
            return UpdateResult(
                success=False,
                updated_apps=[],
                failed_apps=context.app_names if context.app_names else [],
                up_to_date_apps=[],
                update_infos=[],
                message=message,
            )

        apps_to_update = [info for info in update_infos if info.has_update]
        apps_up_to_date = [info for info in update_infos if not info.has_update]

        if apps_up_to_date:
            print(f"✅ {len(apps_up_to_date)} app(s) already up to date")

        if not apps_to_update:
            message = "All specified apps are up to date!"
            print(message)
            return UpdateResult(
                success=True,
                updated_apps=[],
                failed_apps=[],
                up_to_date_apps=[info.app_name for info in apps_up_to_date],
                update_infos=update_infos,
                message=message,
            )

        print(f"📦 Updating {len(apps_to_update)} app(s) that need updates...")

        # Show which apps will be updated
        for info in apps_to_update:
            print(f"   • {info.app_name}: {info.current_version} → {info.latest_version}")

        print()  # Empty line for better spacing

        # Perform updates with suppressed logging
        results = await self._execute_updates(
            context, [info.app_name for info in apps_to_update]
        )

        # Categorize results
        updated_apps: list[str] = []
        failed_apps: list[str] = []

        for app_name, success in results.items():
            if success:
                updated_apps.append(app_name)
            else:
                failed_apps.append(app_name)

        # Create result
        success = len(failed_apps) == 0
        up_to_date_list = [info.app_name for info in apps_up_to_date]

        updated_count = len(updated_apps)
        failed_count = len(failed_apps)

        if updated_count > 0 and failed_count == 0:
            message = f"Successfully updated {updated_count} app(s)"
        elif updated_count > 0 and failed_count > 0:
            message = f"Updated {updated_count} app(s), {failed_count} failed"
        else:
            message = f"Failed to update {failed_count} app(s)"

        return UpdateResult(
            success=success,
            updated_apps=updated_apps,
            failed_apps=failed_apps,
            up_to_date_apps=up_to_date_list,
            update_infos=update_infos,
            message=message,
        )

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
        # Temporarily suppress console logging during downloads
        logger.set_console_level_temporarily("ERROR")

        try:
            return await context.update_manager.update_multiple_apps(app_names)
        finally:
            # Restore normal logging
            logger.restore_console_level()
