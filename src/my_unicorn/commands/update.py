"""Update command handler for my-unicorn CLI.

Simplified to use direct display functions instead of UpdateResult objects.
"""

from argparse import Namespace

from my_unicorn.logger import get_logger, temporary_console_level
from my_unicorn.progress import get_progress_service, progress_session
from my_unicorn.utils import display_update_error, display_update_summary

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
        with temporary_console_level("INFO"):
            # Get target apps
            target_apps = self._get_target_apps(app_names)
            if not target_apps:
                logger.info("No apps to check.")
                return

            # Check for updates with progress message
            update_infos = await self.update_manager.check_updates(
                app_names=target_apps,
                refresh_cache=refresh_cache,
            )

            if not update_infos:
                logger.info("Failed to check for updates.")
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
        with temporary_console_level("INFO"):
            # Get target apps
            target_apps = self._get_target_apps(app_names)
            if not target_apps:
                logger.info("No apps to update.")
                return

            # Check for updates first (without progress bar)
            update_infos = await self.update_manager.check_updates(
                app_names=target_apps,
                refresh_cache=refresh_cache,
            )

            if not update_infos:
                logger.info("Failed to check for updates.")
                return

            # Filter to apps needing updates
            apps_to_update = [
                info.app_name for info in update_infos if info.has_update
            ]

            # If no updates needed, return early without progress bar
            if not apps_to_update:
                logger.info("")  # Empty line
                logger.info(
                    "✅ All %s app(s) are up to date", len(update_infos)
                )
                logger.debug(
                    "No updates needed for %s app(s)", len(update_infos)
                )
                return

            # Display update plan BEFORE starting progress session
            # to avoid print() interference with progress display
            self._display_update_plan(update_infos)

        # Only start progress session if there are apps to update
        async with progress_session():
            progress_service = get_progress_service()

            # Create shared API task
            api_task_id = await progress_service.create_api_fetching_task(
                name="GitHub Releases",
                description="🌐 Fetching release information...",
            )

            # Set total to number of apps being updated
            await progress_service.update_task(
                api_task_id,
                total=float(len(apps_to_update)),
                completed=0.0,
            )

            self.update_manager._shared_api_task_id = api_task_id

            try:
                # Perform updates - pass update_infos to eliminate redundant
                # cache lookups (optimization: reuses in-memory release data)
                (
                    update_results,
                    error_reasons,
                ) = await self.update_manager.update_multiple_apps(
                    apps_to_update, update_infos=update_infos
                )

                await progress_service.finish_task(api_task_id, success=True)

            except Exception:
                await progress_service.finish_task(api_task_id, success=False)
                raise
            finally:
                self.update_manager._shared_api_task_id = None

        # Display results AFTER progress session ends to avoid visual conflicts
        updated_apps = [
            app for app, success in update_results.items() if success
        ]
        failed_apps = [
            app for app, success in update_results.items() if not success
        ]
        up_to_date_apps = [
            info.app_name for info in update_infos if not info.has_update
        ]

        # Store error reasons in UpdateInfo objects
        for info in update_infos:
            if info.app_name in error_reasons:
                info.error_reason = error_reasons[info.app_name]

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
            total = len(update_infos)
            message = f"Successfully updated {updated_count}/{total} app(s)"
        elif updated_count > 0 and failed_count > 0:
            message = f"Updated {updated_count} app(s), {failed_count} failed"
        elif failed_count > 0:
            total = len(update_infos)
            message = f"Failed to update {failed_count}/{total} app(s)"
        else:
            message = f"All {len(update_infos)} app(s) processed"

        logger.debug("Update operation completed: %s", message)

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
            logger.info("⚠️  Apps not found: %s", ", ".join(invalid_apps))
            if installed_apps:
                logger.info("   Installed apps: %s", ", ".join(installed_apps))

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

            logger.info(
                "%s %s %s",
                f"{info.app_name:<20}",
                f"{status:<20}",
                version_info,
            )

            if info.has_update:
                has_updates = True

        if has_updates:
            logger.info("")
            logger.info("Run 'my-unicorn update' to install updates.")

    def _display_update_plan(self, update_infos: list) -> None:
        """Display which apps will be updated.

        Args:
            update_infos: List of UpdateInfo objects.

        """
        apps_with_updates = [info for info in update_infos if info.has_update]

        if apps_with_updates:
            logger.info("📦 Updating %s app(s):", len(apps_with_updates))
            for info in apps_with_updates:
                version_str = f"{info.current_version} → {info.latest_version}"
                logger.info("   • %s: %s", info.app_name, version_str)
            logger.info("")  # Empty line

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
