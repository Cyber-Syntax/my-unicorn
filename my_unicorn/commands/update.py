"""Update command handler for my-unicorn CLI.

This module handles the updating of installed AppImages, providing
comprehensive update checking and batch update capabilities.
"""

from argparse import Namespace

from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


class UpdateHandler(BaseCommandHandler):
    """Handler for update command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the update command."""
        # Parse and validate app names
        app_names = self._parse_app_names(args.apps) if args.apps else None

        if app_names:
            app_names = self._validate_installed_apps(app_names)
            if not app_names:
                return

        if args.check_only:
            await self._check_for_updates(app_names)
        else:
            await self._perform_updates(app_names)

    def _parse_app_names(self, app_args: list[str]) -> list[str]:
        """Parse app names from command arguments, handling comma-separated values."""
        return self._expand_comma_separated_targets(app_args)

    def _validate_installed_apps(self, app_names: list[str]) -> list[str] | None:
        """Validate that specified apps are installed."""
        installed_apps = self.config_manager.list_installed_apps()
        valid_apps = []
        invalid_apps = []

        for app in app_names:
            if app.lower() in [installed.lower() for installed in installed_apps]:
                # Find correct case
                for installed in installed_apps:
                    if installed.lower() == app.lower():
                        valid_apps.append(installed)
                        break
            else:
                invalid_apps.append(app)

        if invalid_apps:
            print("❌ Apps not installed:")
            for app in invalid_apps:
                # Suggest similar installed apps
                suggestions = [inst for inst in installed_apps if app.lower() in inst.lower()][
                    :2
                ]
                if suggestions:
                    print(f"   • {app} (did you mean: {', '.join(suggestions)}?)")
                else:
                    print(f"   • {app}")

            if not valid_apps:
                print("\nNo valid apps to update.")
                return None

        return valid_apps

    async def _check_for_updates(self, app_names: list[str] | None) -> None:
        """Check for available updates without installing them."""
        update_infos = await self.update_manager.check_all_updates(app_names)

        if not update_infos:
            print("No installed apps found to check.")
            return

        has_updates = False
        for info in update_infos:
            status = "📦 Update available" if info.has_update else "✅ Up to date"
            version_info = (
                f"{info.current_version} -> {info.latest_version}"
                if info.has_update
                else info.current_version
            )
            print(
                f"{info.app_name:<20} {status:<20} {self._format_version_display(version_info)}"
            )
            if info.has_update:
                has_updates = True

        if has_updates:
            print("\nRun 'my-unicorn update' to install updates.")

    async def _perform_updates(self, app_names: list[str] | None) -> None:
        """Perform updates for specified or all apps."""
        if app_names:
            await self._update_specific_apps(app_names)
        else:
            await self._update_all_apps()

    async def _update_specific_apps(self, app_names: list[str]) -> None:
        """Update specific apps."""
        print(f"🔄 Updating {len(app_names)} app(s): {', '.join(app_names)}")

        # Check which apps actually need updates
        print("🔍 Checking for updates...")
        update_infos = await self.update_manager.check_all_updates(app_names)
        apps_to_update = [info for info in update_infos if info.has_update]
        apps_up_to_date = [info for info in update_infos if not info.has_update]

        if apps_up_to_date:
            print(f"✅ {len(apps_up_to_date)} app(s) already up to date")

        if not apps_to_update:
            print("All specified apps are up to date!")
            return

        print(f"📦 Updating {len(apps_to_update)} app(s) that need updates...")

        # Perform updates with suppressed logging
        results = await self._execute_updates([info.app_name for info in apps_to_update])
        self._print_update_summary(results, apps_to_update)

    async def _update_all_apps(self) -> None:
        """Update all installed apps."""
        installed_apps = self.config_manager.list_installed_apps()
        if not installed_apps:
            print("No installed apps found to update.")
            return

        print(f"🔄 Checking all {len(installed_apps)} installed app(s) for updates...")

        # Check which apps need updates
        update_infos = await self.update_manager.check_all_updates(installed_apps)
        apps_to_update = [info for info in update_infos if info.has_update]
        apps_up_to_date = [info for info in update_infos if not info.has_update]

        if apps_up_to_date:
            print(f"✅ {len(apps_up_to_date)} app(s) already up to date")

        if not apps_to_update:
            print("All apps are up to date!")
            return

        print(f"📦 Updating {len(apps_to_update)} app(s) that need updates...")

        # Show which apps will be updated
        for info in apps_to_update:
            print(f"   • {info.app_name}: {info.current_version} → {info.latest_version}")

        print()  # Empty line for better spacing

        # Perform updates with suppressed logging
        results = await self._execute_updates([info.app_name for info in apps_to_update])
        self._print_update_summary(results, apps_to_update)

    async def _execute_updates(self, app_names: list[str]) -> dict[str, bool]:
        """Execute updates with temporarily suppressed console logging."""
        # Temporarily suppress console logging during downloads
        logger.set_console_level_temporarily("ERROR")

        try:
            return await self.update_manager.update_multiple_apps(app_names)
        finally:
            # Restore normal logging
            logger.restore_console_level()

    def _print_update_summary(self, results: dict[str, bool], apps_to_update: list) -> None:
        """Print summary of update results."""
        print("\n📦 Update Summary:")
        print("-" * 50)

        updated_count = 0
        failed_count = 0

        for app_name, success in results.items():
            if success:
                updated_count += 1
                # Find the version info for this app
                app_info = next(
                    (info for info in apps_to_update if info.app_name == app_name), None
                )
                if app_info:
                    print(f"{app_name:<25} ✅ Updated to {app_info.latest_version}")
                else:
                    print(f"{app_name:<25} ✅ Updated")
            else:
                failed_count += 1
                print(f"{app_name:<25} ❌ Update failed")

        # Show summary stats
        if updated_count > 0:
            print(f"\n🎉 Successfully updated {updated_count} app(s)")
        if failed_count > 0:
            print(f"❌ {failed_count} app(s) failed to update")

    def _format_version_display(self, version_info: str) -> str:
        """Format version information for display."""
        # Truncate long version strings for better display
        if len(version_info) > 40:
            return version_info[:37] + "..."
        return version_info
