"""Update all apps strategy implementation.

This module implements the strategy for updating all installed apps.
It discovers all installed apps, checks for updates, and performs updates
on all apps that have updates available.
"""

from my_unicorn.logger import get_logger
from my_unicorn.services.progress import get_progress_service, progress_session

from ..update import UpdateInfo
from .update import UpdateContext, UpdateResult, UpdateStrategy

logger = get_logger(__name__)


class UpdateAllAppsStrategy(UpdateStrategy):
    """Strategy for updating all installed apps.

    This strategy discovers all installed apps from the configuration,
    checks which ones need updates, and performs updates on all apps
    that have updates available.
    """

    def validate_inputs(self, context: UpdateContext) -> bool:
        """Validate inputs for update all apps strategy.

        Args:
            context: Update context to validate

        Returns:
            True if inputs are valid, False otherwise

        """
        if context.app_names:
            logger.warning(
                "app_names specified but will be ignored in update all apps strategy"
            )

        # Check if any apps are installed
        installed_apps = context.config_manager.list_installed_apps()
        if not installed_apps:
            print("No installed apps found to update.")
            return False

        return True

    async def execute(self, context: UpdateContext) -> UpdateResult:
        """Execute the update all apps strategy.

        Args:
            context: Update context with dependencies and configuration

        Returns:
            UpdateResult with update results

        """
        logger.debug("Executing update all apps strategy")

        # Get all installed apps
        installed_apps = context.config_manager.list_installed_apps()

        # Check which apps need updates and perform updates in single session

        async with progress_session():
            progress_service = get_progress_service()

            # Create minimal API progress task - let API calls drive the count
            api_task_id = await progress_service.create_api_fetching_task(
                endpoint="API assets", total_requests=1
            )

            # Set shared task for update manager
            context.update_manager._shared_api_task_id = api_task_id

            apps_to_update: list[UpdateInfo] = []
            apps_up_to_date: list[UpdateInfo] = []
            results: dict[str, bool] = {}

            try:
                # Check which apps need updates
                phase1_result = await self._check_for_updates_phase(context, installed_apps)

                if phase1_result is None:
                    # This shouldn't happen for update_all, but keeping for consistency
                    message = "Failed to check updates for installed apps."
                    return UpdateResult(
                        success=False,
                        updated_apps=[],
                        failed_apps=installed_apps,
                        up_to_date_apps=[],
                        update_infos=[],
                        message=message,
                    )

                apps_to_update, apps_up_to_date, update_infos = phase1_result

                if not apps_to_update:
                    message = "All apps are up to date!"
                    # Finish API progress task
                    await progress_service.finish_task(api_task_id, success=True)
                    return UpdateResult(
                        success=True,
                        updated_apps=[],
                        failed_apps=[],
                        up_to_date_apps=[info.app_name for info in apps_up_to_date],
                        update_infos=update_infos,
                        message=message,
                    )

                # Perform updates on apps that need updating
                results = await self._perform_updates_phase(context, apps_to_update)

                # Finish API progress task
                await progress_service.finish_task(api_task_id, success=True)

            except Exception:
                # Finish API progress task with error
                await progress_service.finish_task(api_task_id, success=False)
                raise
            finally:
                # Clean up shared task
                context.update_manager._shared_api_task_id = None

        # Categorize and create final result
        updated_apps, failed_apps = self._categorize_update_results(results)
        return self._create_final_result_for_all(
            updated_apps, failed_apps, apps_up_to_date, update_infos
        )

    async def _check_for_updates_phase(
        self, context: UpdateContext, installed_apps: list[str]
    ) -> tuple[list[UpdateInfo], list[UpdateInfo], list[UpdateInfo]] | None:
        """Check which apps need updates and categorize them.

        Args:
            context: Update context with dependencies and configuration
            installed_apps: List of all installed apps to check

        Returns:
            Tuple of (apps_to_update, apps_up_to_date, all_update_infos) or None if error

        """
        update_infos = await context.update_manager.check_all_updates_with_progress(
            installed_apps, refresh_cache=context.refresh_cache
        )

        apps_to_update = [info for info in update_infos if info.has_update]
        apps_up_to_date = [info for info in update_infos if not info.has_update]

        if apps_up_to_date:
            print(f"✅ {len(apps_up_to_date)} app(s) already up to date")

        if not apps_to_update:
            print("All apps are up to date!")

        return apps_to_update, apps_up_to_date, update_infos

    async def _perform_updates_phase(
        self, context: UpdateContext, apps_to_update: list[UpdateInfo]
    ) -> dict[str, bool]:
        """Perform updates on apps that need updating.

        Args:
            context: Update context with dependencies
            apps_to_update: List of apps that need updates

        Returns:
            Dictionary mapping app names to success status

        """
        # Show which apps will be updated
        for info in apps_to_update:
            print(f"   • {info.app_name}: {info.current_version} → {info.latest_version}")

        print()  # Empty line for better spacing

        # Perform the actual updates
        return await self._execute_updates(context, [info.app_name for info in apps_to_update])

    def _create_final_result_for_all(
        self,
        updated_apps: list[str],
        failed_apps: list[str],
        apps_up_to_date: list[UpdateInfo],
        update_infos: list[UpdateInfo],
    ) -> UpdateResult:
        """Create the final UpdateResult for update all strategy.

        Args:
            updated_apps: List of successfully updated app names
            failed_apps: List of failed app names
            apps_up_to_date: List of apps that were already up to date
            update_infos: All update information

        Returns:
            Final UpdateResult object

        """
        success = len(failed_apps) == 0
        up_to_date_list = [info.app_name for info in apps_up_to_date]

        updated_count = len(updated_apps)
        failed_count = len(failed_apps)
        total_checked = len(update_infos)

        if updated_count > 0 and failed_count == 0:
            message = f"Successfully updated {updated_count} out of {total_checked} app(s)"
        elif updated_count > 0 and failed_count > 0:
            message = (
                f"Updated {updated_count} app(s), {failed_count} failed "
                f"out of {total_checked} checked"
            )
        else:
            message = f"Failed to update {failed_count} out of {total_checked} app(s)"

        return UpdateResult(
            success=success,
            updated_apps=updated_apps,
            failed_apps=failed_apps,
            up_to_date_apps=up_to_date_list,
            update_infos=update_infos,
            message=message,
        )
