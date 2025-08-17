"""Utility for displaying update results consistently.

This module provides functions for formatting and displaying update results
in a consistent manner across all update strategies.
"""

from ..logger import get_logger
from ..update import UpdateInfo
from .update_strategy import UpdateResult

logger = get_logger(__name__)


class UpdateResultDisplay:
    """Utility class for displaying update results consistently."""

    @staticmethod
    def display_summary(result: UpdateResult) -> None:
        """Display a comprehensive summary of update results.

        Args:
            result: UpdateResult object containing all result information

        """
        if not result.update_infos:
            print(result.message)
            return

        if result.updated_apps or result.failed_apps:
            UpdateResultDisplay._display_update_summary(result)
        else:
            UpdateResultDisplay._display_check_summary(result)

    @staticmethod
    def _display_update_summary(result: UpdateResult) -> None:
        """Display summary for actual update operations.

        Args:
            result: UpdateResult with update operation results

        """
        print("\n📦 Update Summary:")
        print("-" * 50)

        updated_count = len(result.updated_apps)
        failed_count = len(result.failed_apps)

        # Show individual results
        for app_name in result.updated_apps:
            app_info = UpdateResultDisplay._find_app_info(app_name, result.update_infos)
            if app_info:
                print(f"{app_name:<25} ✅ Updated to {app_info.latest_version}")
            else:
                print(f"{app_name:<25} ✅ Updated")

        for app_name in result.failed_apps:
            print(f"{app_name:<25} ❌ Update failed")

        # Show summary stats
        if updated_count > 0:
            print(f"\n🎉 Successfully updated {updated_count} app(s)")
        if failed_count > 0:
            print(f"❌ {failed_count} app(s) failed to update")

    @staticmethod
    def _display_check_summary(result: UpdateResult) -> None:
        """Display summary for check-only operations.

        Args:
            result: UpdateResult with check operation results

        """
        total_apps = len(result.update_infos)
        apps_with_updates = sum(1 for info in result.update_infos if info.has_update)

        if total_apps == 0:
            print("No apps to check.")
            return

        print("\n📋 Check Summary:")
        print("-" * 50)
        print(f"Total apps checked: {total_apps}")
        print(f"Updates available: {apps_with_updates}")
        print(f"Up to date: {total_apps - apps_with_updates}")

        if result.message:
            print(f"\n{result.message}")

    @staticmethod
    def display_detailed_results(result: UpdateResult) -> None:
        """Display detailed results including version information.

        Args:
            result: UpdateResult with detailed information

        """
        if not result.update_infos:
            print(result.message)
            return

        print("\n📊 Detailed Results:")
        print("-" * 70)
        print(f"{'App Name':<20} {'Status':<20} {'Version Info':<25}")
        print("-" * 70)

        for info in result.update_infos:
            status = UpdateResultDisplay._get_app_status(info, result)
            version_info = UpdateResultDisplay._format_version_info(info)
            print(f"{info.app_name:<20} {status:<20} {version_info:<25}")

    @staticmethod
    def _get_app_status(info: UpdateInfo, result: UpdateResult) -> str:
        """Get the status string for an app.

        Args:
            info: UpdateInfo for the app
            result: UpdateResult containing operation results

        Returns:
            Status string for display

        """
        if info.app_name in result.updated_apps:
            return "✅ Updated"
        elif info.app_name in result.failed_apps:
            return "❌ Failed"
        elif info.has_update:
            return "📦 Update available"
        else:
            return "✅ Up to date"

    @staticmethod
    def _format_version_info(info: UpdateInfo) -> str:
        """Format version information for display.

        Args:
            info: UpdateInfo containing version information

        Returns:
            Formatted version string

        """
        if info.has_update:
            version_str = f"{info.current_version} → {info.latest_version}"
        else:
            version_str = info.current_version

        # Truncate long version strings
        if len(version_str) > 40:
            return version_str[:37] + "..."
        return version_str

    @staticmethod
    def _find_app_info(app_name: str, update_infos: list[UpdateInfo]) -> UpdateInfo | None:
        """Find UpdateInfo for a specific app.

        Args:
            app_name: Name of the app to find
            update_infos: List of UpdateInfo objects

        Returns:
            UpdateInfo for the app, or None if not found

        """
        for info in update_infos:
            if info.app_name == app_name:
                return info
        return None

    @staticmethod
    def display_progress(message: str) -> None:
        """Display a progress message.

        Args:
            message: Progress message to display

        """
        print(f"🔄 {message}")

    @staticmethod
    def display_success(message: str) -> None:
        """Display a success message.

        Args:
            message: Success message to display

        """
        print(f"✅ {message}")

    @staticmethod
    def display_error(message: str) -> None:
        """Display an error message.

        Args:
            message: Error message to display

        """
        print(f"❌ {message}")

    @staticmethod
    def display_warning(message: str) -> None:
        """Display a warning message.

        Args:
            message: Warning message to display

        """
        print(f"⚠️  {message}")
