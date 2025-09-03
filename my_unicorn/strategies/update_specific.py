"""Update specific apps strategy implementation.

This module implements the strategy for updating only specified apps.
It validates the requested apps, checks for updates, and performs updates
only on the apps that actually need updating.
"""

from my_unicorn.logger import get_logger
from my_unicorn.services.progress import get_progress_service, progress_session

from .update import UpdateContext, UpdateInfo, UpdateResult, UpdateStrategy

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
        if context.app_names is None:
            raise ValueError("app_names should not be None after validation")

        logger.debug("Executing update strategy for specific apps: %s", context.app_names)

        # Check which apps actually need updates and perform updates in single session

        async with progress_session():
            progress_service = get_progress_service()

            # Create shared API progress task for all GitHub API calls
            api_task_id = await progress_service.create_api_fetching_task(
                endpoint="API assets",
                total_requests=self._calculate_total_api_requests(context),
            )

            # Set shared task for update manager
            context.update_manager._shared_api_task_id = api_task_id

            apps_to_update: list[UpdateInfo] = []
            apps_up_to_date: list[UpdateInfo] = []
            results: dict[str, bool] = {}

            try:
                # Check which apps need updates
                phase1_result = await self._check_for_updates_phase(context)

                if phase1_result is None:
                    # Error occurred during update check
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

                apps_to_update, apps_up_to_date = phase1_result

                if not apps_to_update:
                    message = "All specified apps are up to date!"
                    # Finish API progress task
                    await progress_service.finish_task(api_task_id, success=True)
                    return UpdateResult(
                        success=True,
                        updated_apps=[],
                        failed_apps=[],
                        up_to_date_apps=[info.app_name for info in apps_up_to_date],
                        update_infos=apps_to_update + apps_up_to_date,
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
        return self._create_final_result(
            updated_apps, failed_apps, apps_up_to_date, apps_to_update
        )

    def _calculate_total_api_requests(self, context: UpdateContext) -> int:
        """Calculate the total number of API requests needed for the update process.

        Args:
            context: Update context containing app names

        Returns:
            Total number of API requests needed

        """
        app_count = len(context.app_names) if context.app_names else 0
        # Conservatively estimate 2 API requests per app
        # (1 for check, 1 for download info)
        return app_count * 2

    def _is_update_successful(self, failed_apps: list[str]) -> bool:
        """Determine if the overall update process was successful.

        Args:
            failed_apps: List of apps that failed to update

        Returns:
            True if no apps failed, False otherwise

        """
        return len(failed_apps) == 0

    def _extract_up_to_date_names(self, apps_up_to_date: list[UpdateInfo]) -> list[str]:
        """Extract app names from list of up-to-date UpdateInfo objects.

        Args:
            apps_up_to_date: List of apps that were already up to date

        Returns:
            List of app names that were up to date

        """
        return [info.app_name for info in apps_up_to_date]

    def _generate_result_message(self, updated_apps: list[str], failed_apps: list[str]) -> str:
        """Generate appropriate result message based on update outcomes.

        Args:
            updated_apps: List of successfully updated apps
            failed_apps: List of apps that failed to update

        Returns:
            Descriptive message about the update results

        """
        updated_count = len(updated_apps)
        failed_count = len(failed_apps)

        if updated_count > 0 and failed_count == 0:
            return f"Successfully updated {updated_count} app(s)"
        elif updated_count > 0 and failed_count > 0:
            return f"Updated {updated_count} app(s), {failed_count} failed"
        else:
            return f"Failed to update {failed_count} app(s)"

    def _create_final_result(
        self,
        updated_apps: list[str],
        failed_apps: list[str],
        apps_up_to_date: list[UpdateInfo],
        apps_to_update: list[UpdateInfo],
    ) -> UpdateResult:
        """Create the final UpdateResult with appropriate success status and message.

        Args:
            updated_apps: List of successfully updated app names
            failed_apps: List of failed app names
            apps_up_to_date: List of apps that were already up to date
            apps_to_update: List of apps that needed updates

        Returns:
            Final UpdateResult object

        """
        return UpdateResult(
            success=self._is_update_successful(failed_apps),
            updated_apps=updated_apps,
            failed_apps=failed_apps,
            up_to_date_apps=self._extract_up_to_date_names(apps_up_to_date),
            update_infos=apps_to_update + apps_up_to_date,
            message=self._generate_result_message(updated_apps, failed_apps),
        )

    async def _check_for_updates_phase(
        self, context: UpdateContext
    ) -> tuple[list[UpdateInfo], list[UpdateInfo]] | None:
        """Check which apps need updates and categorize them.

        Args:
            context: Update context with dependencies and configuration

        Returns:
            Tuple of (apps_to_update, apps_up_to_date) or None if error occurred

        """
        update_infos = await context.update_manager.check_all_updates_with_progress(
            context.app_names, refresh_cache=context.refresh_cache
        )

        # Detect if update_infos is empty due to authentication failure or other errors
        if not update_infos:
            logger.error(
                "Failed to check updates for specified apps. "
                "This may be due to invalid GitHub Personal Access Token (PAT)."
            )
            return None

        apps_to_update = [info for info in update_infos if info.has_update]
        apps_up_to_date = [info for info in update_infos if not info.has_update]

        if apps_up_to_date:
            print(f"✅ {len(apps_up_to_date)} app(s) already up to date")

        if not apps_to_update:
            print("All specified apps are up to date!")

        return apps_to_update, apps_up_to_date

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
