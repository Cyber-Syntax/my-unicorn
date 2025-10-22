"""Update command handler for my-unicorn CLI.

Simplified to use direct display functions instead of UpdateResult objects.
"""

from argparse import Namespace

from ..logger import get_logger
from ..services.progress import get_progress_service, progress_session
from ..utils import display_update_error, display_update_summary
from .base import BaseCommandHandler

logger = get_logger(__name__)

# Constants
MAX_VERSION_DISPLAY_LENGTH = 40


class UpdateHandler(BaseCommandHandler):
    """Handler for update command operations.

    Simplified to directly use UpdateManager without template overhead.
    """

    async def execute(self, args: Namespace) -> None:
        """Execute the update command.

        Args:
            args: Parsed command-line arguments containing update parameters.

        """
        try:
            # Parse arguments
            app_names = self._parse_app_names(args) if args.apps else None
            check_only = getattr(args, "check_only", False)
            refresh_cache = getattr(args, "refresh_cache", False)

            # Execute based on mode
            if check_only:
                await self._check_for_updates(app_names, refresh_cache)
            else:
                await self._perform_updates(app_names, refresh_cache)

        except Exception as e:
            logger.error("Update command failed: %s", e)
            display_update_error(f"Update operation failed: {e}")

    async def _check_for_updates(
        self, app_names: list[str] | None, refresh_cache: bool
    ) -> None:
        """Check for updates without installing them.

        Args:
            app_names: Specific apps to check, or None for all.
            refresh_cache: Whether to bypass cache.

        """
        # Get target apps
        target_apps = self._get_target_apps(app_names)
        if not target_apps:
            print("No apps to check.")
            return

        # Check for updates with progress message
        update_infos = await self.update_manager.check_updates(
            app_names=target_apps,
            show_progress=True,
            refresh_cache=refresh_cache,
        )

        if not update_infos:
            print("Failed to check for updates.")
            return

        # Display check results
        self._display_check_results(update_infos)

        logger.debug(
            "Check operation completed for %s app(s)", len(update_infos)
        )

    async def _perform_updates(
        self, app_names: list[str] | None, refresh_cache: bool
    ) -> None:
        """Perform actual updates on apps.

        Args:
            app_names: Specific apps to update, or None for all.
            refresh_cache: Whether to bypass cache.

        """
        # Get target apps
        target_apps = self._get_target_apps(app_names)
        if not target_apps:
            print("No apps to update.")
            return

        # Check for updates first (without progress bar)
        update_infos = await self.update_manager.check_updates(
            app_names=target_apps,
            show_progress=True,
            refresh_cache=refresh_cache,
        )

        if not update_infos:
            print("Failed to check for updates.")
            return

        # Filter to apps needing updates
        apps_to_update = [
            info.app_name for info in update_infos if info.has_update
        ]

        # If no updates needed, return early without progress bar
        if not apps_to_update:
            up_to_date = [info.app_name for info in update_infos]
            print(f"\n✅ All {len(update_infos)} app(s) are up to date")
            logger.debug("No updates needed for %s app(s)", len(update_infos))
            return

        # Only start progress session if there are apps to update
        async with progress_session():
            progress_service = get_progress_service()

            # Create shared API task
            api_task_id = await progress_service.create_api_fetching_task(
                endpoint="API assets", total_requests=1
            )
            self.update_manager._shared_api_task_id = api_task_id

            try:
                # Display update plan
                self._display_update_plan(update_infos)

                # Perform updates - pass update_infos to eliminate redundant
                # cache lookups (optimization: reuses in-memory release data)
                update_results = (
                    await self.update_manager.update_multiple_apps(
                        apps_to_update, update_infos=update_infos
                    )
                )

                await progress_service.finish_task(api_task_id, success=True)

                # Display results using new display functions
                updated_apps = [
                    app for app, success in update_results.items() if success
                ]
                failed_apps = [
                    app
                    for app, success in update_results.items()
                    if not success
                ]
                up_to_date_apps = [
                    info.app_name
                    for info in update_infos
                    if not info.has_update
                ]

                display_update_summary(
                    updated_apps=updated_apps,
                    failed_apps=failed_apps,
                    up_to_date_apps=up_to_date_apps,
                    update_infos=update_infos,
                    check_only=False,
                )

                # Log final status
                updated_count = len(updated_apps)
                failed_count = len(failed_apps)
                if updated_count > 0 and failed_count == 0:
                    message = f"Successfully updated {updated_count}/{len(update_infos)} app(s)"
                elif updated_count > 0 and failed_count > 0:
                    message = f"Updated {updated_count} app(s), {failed_count} failed"
                elif failed_count > 0:
                    message = f"Failed to update {failed_count}/{len(update_infos)} app(s)"
                else:
                    message = f"All {len(update_infos)} app(s) processed"

                logger.debug("Update operation completed: %s", message)

            except Exception:
                await progress_service.finish_task(api_task_id, success=False)
                raise
            finally:
                self.update_manager._shared_api_task_id = None

    def _get_target_apps(self, app_names: list[str] | None) -> list[str]:
        """Get target apps with validation.

        Args:
            app_names: Specific apps or None for all.

        Returns:
            List of valid installed app names.

        """
        installed_apps = self.config_manager.list_installed_apps()

        # If no specific apps, return all installed
        if not app_names:
            return installed_apps

        # Validate specific apps
        valid_apps = []
        invalid_apps = []

        for app in app_names:
            # Case-insensitive matching
            matched = False
            for installed in installed_apps:
                if installed.lower() == app.lower():
                    valid_apps.append(installed)
                    matched = True
                    break

            if not matched:
                invalid_apps.append(app)

        # Print invalid apps
        if invalid_apps:
            print(f"⚠️  Apps not found: {', '.join(invalid_apps)}")
            if installed_apps:
                print(f"   Installed apps: {', '.join(installed_apps)}")

        return valid_apps

    def _display_check_results(self, update_infos: list) -> None:
        """Display check results in formatted table.

        Args:
            update_infos: List of UpdateInfo objects.

        """
        has_updates = False

        for info in update_infos:
            if info.has_update:
                status = "📦 Update available"
            else:
                status = "✅ Up to date"

            version_info = (
                f"{info.current_version} -> {info.latest_version}"
                if info.has_update
                else info.current_version
            )

            # Truncate long versions
            if len(version_info) > MAX_VERSION_DISPLAY_LENGTH:
                version_info = version_info[:37] + "..."

            print(f"{info.app_name:<20} {status:<20} {version_info}")

            if info.has_update:
                has_updates = True

        if has_updates:
            print("\nRun 'my-unicorn update' to install updates.")

    def _display_update_plan(self, update_infos: list) -> None:
        """Display which apps will be updated.

        Args:
            update_infos: List of UpdateInfo objects.

        """
        apps_with_updates = [info for info in update_infos if info.has_update]

        if apps_with_updates:
            print(f"📦 Updating {len(apps_with_updates)} app(s):")
            for info in apps_with_updates:
                print(
                    f"   • {info.app_name}: {info.current_version} → {info.latest_version}"
                )
            print()  # Empty line

    def _parse_app_names(self, args: Namespace) -> list[str]:
        """Parse app names from command arguments.

        Args:
            args: Command arguments.

        Returns:
            List of app names.

        """
        if not args.apps:
            return []

        return self._expand_comma_separated_targets(args.apps)
