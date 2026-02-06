"""Display utility functions for update results.

This module provides functions for formatting and displaying update results
in a consistent manner across all update operations.

Note:
    These functions use print() for direct console output to ensure
    messages are always visible to users regardless of logger configuration.
"""
# ruff: noqa: T201

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my_unicorn.config import ConfigManager
    from my_unicorn.core.update.info import UpdateInfo

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def display_update_summary(
    updated_apps: list[str],
    failed_apps: list[str],
    up_to_date_apps: list[str],  # noqa: ARG001
    update_infos: list["UpdateInfo"],
    check_only: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Display a comprehensive summary of update results.

    Args:
        updated_apps: List of successfully updated app names.
        failed_apps: List of failed app names.
        up_to_date_apps: List of apps that are up to date.
        update_infos: List of UpdateInfo objects with details.
        check_only: If True, display check-only summary instead of
            update summary.

    """
    if not update_infos:
        print("No apps to process.")
        return

    if check_only:
        _display_check_only_summary(update_infos)
    else:
        _display_update_operation_summary(
            updated_apps, failed_apps, update_infos
        )


def _display_update_operation_summary(
    updated_apps: list[str],
    failed_apps: list[str],
    update_infos: list["UpdateInfo"],
) -> None:
    """Display summary for actual update operations.

    Args:
        updated_apps: List of successfully updated app names.
        failed_apps: List of failed app names.
        update_infos: List of UpdateInfo objects with details.

    """
    print("\n📦 Update Summary:")
    print("-" * 50)

    updated_count = len(updated_apps)
    failed_count = len(failed_apps)

    # Show individual results
    for app_name in updated_apps:
        app_info = _find_update_info(app_name, update_infos)
        version_info = (
            f"{app_info.current_version} → {app_info.latest_version}"
        )
        print(f"{app_name:<25} ✅ {version_info}")

    for app_name in failed_apps:
        app_info = _find_update_info(app_name, update_infos)
        print(f"{app_name:<25} ❌ Update failed")
        # Display error reason if available
        if app_info.error_reason:
            print(f"{'':>25}    → {app_info.error_reason}")

    # Show summary stats
    print()
    if updated_count > 0:
        print(f"🎉 Successfully updated {updated_count} app(s)")
    if failed_count > 0:
        print(f"❌ {failed_count} app(s) failed to update")


def _display_check_only_summary(update_infos: list["UpdateInfo"]) -> None:
    """Display summary for check-only operations.

    Args:
        update_infos: List of UpdateInfo objects with details.

    """
    total_apps = len(update_infos)
    apps_with_updates = sum(1 for info in update_infos if info.has_update)

    if total_apps == 0:
        print("No apps to check.")
        return

    print("\n📋 Check Summary:")
    print("-" * 50)
    print(f"Total apps checked: {total_apps}")
    print(f"Updates available: {apps_with_updates}")
    print(f"Up to date: {total_apps - apps_with_updates}")

    if apps_with_updates > 0:
        print("\nApps with updates available:")
        for info in update_infos:
            if info.has_update:
                version_info = (
                    f"{info.current_version} → {info.latest_version}"
                )
                print(f"  • {info.app_name}: {version_info}")


def display_update_details(
    updated_apps: list[str],
    failed_apps: list[str],
    update_infos: list["UpdateInfo"],
) -> None:
    """Display detailed results including version information.

    Args:
        updated_apps: List of successfully updated app names.
        failed_apps: List of failed app names.
        update_infos: List of UpdateInfo objects with details.

    """
    if not update_infos:
        print("No update information available.")
        return

    print("\n📊 Detailed Results:")
    print("-" * 70)
    print(f"{'App Name':<20} {'Status':<20} {'Version Info':<25}")
    print("-" * 70)

    for info in update_infos:
        status = _get_update_status(info, updated_apps, failed_apps)
        version_info = _format_update_version_info(info)
        print(f"{info.app_name:<20} {status:<20} {version_info:<25}")


def _get_update_status(
    info: "UpdateInfo",
    updated_apps: list[str],
    failed_apps: list[str],
) -> str:
    """Get the status string for an app.

    Args:
        info: UpdateInfo for the app.
        updated_apps: List of successfully updated app names.
        failed_apps: List of failed app names.

    Returns:
        Status string for display.

    """
    if info.app_name in updated_apps:
        return "✅ Updated"
    if info.app_name in failed_apps:
        return "❌ Failed"
    if info.has_update:
        return "📦 Update available"
    return "✅ Up to date"


def _format_update_version_info(info: "UpdateInfo") -> str:
    """Format version information for display.

    Args:
        info: UpdateInfo containing version information.

    Returns:
        Formatted version string.

    """
    if info.has_update:
        version_str = f"{info.current_version} → {info.latest_version}"
    else:
        version_str = info.current_version

    # Truncate long version strings
    if len(version_str) > 40:  # noqa: PLR2004
        return version_str[:37] + "..."
    return version_str


def _find_update_info(
    app_name: str,
    update_infos: list["UpdateInfo"],
) -> "UpdateInfo":
    """Find UpdateInfo for a specific app.

    Args:
        app_name: Name of the app to find.
        update_infos: List of UpdateInfo objects.

    Returns:
        UpdateInfo for the app with default error if not found.

    """
    for info in update_infos:
        if info.app_name == app_name:
            return info
    # Return default error UpdateInfo if not found
    from my_unicorn.core.update.info import UpdateInfo

    return UpdateInfo(
        app_name=app_name,
        error_reason="Update info not found",
    )


def display_update_progress(message: str) -> None:
    """Display a progress message.

    Args:
        message: Progress message to display.

    """
    print(f"🔄 {message}")


def display_update_success(message: str) -> None:
    """Display a success message.

    Args:
        message: Success message to display.

    """
    print(f"✅ {message}")


def display_update_error(message: str) -> None:
    """Display an error message.

    Args:
        message: Error message to display.

    """
    print(f"❌ {message}")


def display_update_warning(message: str) -> None:
    """Display a warning message.

    Args:
        message: Warning message to display.

    """
    print(f"⚠️  {message}")


def display_check_results(results: dict) -> None:
    """Display check-only results from update service.

    Args:
        results: Results dictionary with 'available_updates' key

    """
    if results["available_updates"]:
        logger.info("Updates available:")
        for info in results["available_updates"]:
            logger.info(
                "  %s: %s → %s",
                info["app_name"],
                info["current_version"],
                info["latest_version"],
            )
        logger.info("\nRun 'my-unicorn update' to install updates")
    else:
        logger.info("✅ All apps are up to date")


def display_update_results(results: dict) -> None:  # noqa: C901, PLR0912
    """Display update operation results from update service.

    Args:
        results: Results dictionary with 'updated', 'failed', 'up_to_date',
            and 'update_infos' keys

    """
    updated = results.get("updated", [])
    failed = results.get("failed", [])
    up_to_date = results.get("up_to_date", [])
    update_infos = results.get("update_infos", [])

    # If we have detailed info, use formatted summary
    if update_infos:
        print("\n📦 Update Summary:")
        print("-" * 50)

        # Show updated apps with version info
        for app_name in updated:
            app_info = _find_update_info(app_name, update_infos)
            if app_info:
                version_info = (
                    f"{app_info.current_version} → {app_info.latest_version}"
                )
                print(f"{app_name:<25} ✅ {version_info}")
            else:
                print(f"{app_name:<25} ✅ Updated")

        # Show failed apps with error info
        for app_name in failed:
            app_info = _find_update_info(app_name, update_infos)
            print(f"{app_name:<25} ❌ Update failed")
            if app_info and app_info.error_reason:
                print(f"{'':25}    → {app_info.error_reason}")

        # Show up-to-date apps
        for app_name in up_to_date:
            app_info = _find_update_info(app_name, update_infos)
            if app_info:
                version = app_info.current_version
                print(
                    f"{app_name:<25} ℹ️  Already up to date ({version})"  # noqa: RUF001
                )
            else:
                print(f"{app_name:<25} ℹ️  Already up to date")  # noqa: RUF001

        # Show summary stats
        print()
        if updated:
            print(f"🎉 Successfully updated {len(updated)} app(s)")
        if failed:
            print(f"❌ {len(failed)} app(s) failed to update")
        if up_to_date:
            print(
                f"ℹ️  {len(up_to_date)} app(s) already up to date"  # noqa: RUF001
            )
    else:
        # Fallback to simple logger output
        if updated:
            logger.info("✅ Successfully updated: %s", ", ".join(updated))
        if failed:
            logger.error("❌ Failed to update: %s", ", ".join(failed))
        if up_to_date:
            logger.info("Already up to date: %s", ", ".join(up_to_date))


def display_invalid_apps(
    invalid_apps: list[str], config_manager: "ConfigManager"
) -> None:
    """Display warning about invalid app names.

    Args:
        invalid_apps: List of app names not found
        config_manager: ConfigManager instance for listing installed apps

    """
    if invalid_apps:
        logger.warning("⚠️  Apps not found: %s", ", ".join(invalid_apps))
        installed = config_manager.list_installed_apps()
        if installed:
            logger.info("   Installed apps: %s", ", ".join(installed))
