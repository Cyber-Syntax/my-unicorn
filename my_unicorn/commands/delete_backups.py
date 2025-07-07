#!/usr/bin/env python3
"""Delete backup files command module.

This module provides functionality to delete backup files for applications.
It includes options to delete all backups, delete backups for a specific app,
delete backups older than a specific date, and clean up to keep only a specified
number of backups per app.
"""

import logging
import os

from my_unicorn.commands.base import Command
from my_unicorn.global_config import GlobalConfigManager

logger = logging.getLogger(__name__)


class DeleteBackupsCommand(Command):
    """Command for managing and deleting backup files."""

    def execute(self) -> None:
        """Execute the command to delete backup files."""
        global_config = GlobalConfigManager()

        print("\n=== Delete Old Backups ===")
        print("Options:")
        print("1. Delete all backup files")
        print("2. Delete backups for a specific app")
        print("3. Delete backups older than a specific date")
        print("4. Clean up to keep only max backups per app")
        print("5. Return to main menu")

        choice = input("Enter your choice (1-5): ")

        if choice == "1":
            self._delete_all_backups(global_config)
        elif choice == "2":
            self._delete_app_backups(global_config)
        elif choice == "3":
            self._delete_old_backups(global_config)
        elif choice == "4":
            self._cleanup_to_max_backups(global_config)
        elif choice == "5":
            print("Returning to main menu...")
            return
        else:
            print("Invalid choice. Returning to main menu...")
            return

    def _delete_all_backups(self, global_config: GlobalConfigManager) -> None:
        """Delete all backup files."""
        backup_dir = global_config.expanded_app_backup_storage_path

        if not os.path.exists(backup_dir):
            print(f"Backup directory {backup_dir} does not exist.")
            return

        confirm = input(
            f"Are you sure you want to delete ALL backup files from {backup_dir}? (yes/no): "
        )
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            return

        try:
            file_count = 0
            for filename in os.listdir(backup_dir):
                if filename.lower().endswith(".appimage"):
                    filepath = os.path.join(backup_dir, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        file_count += 1

            if file_count > 0:
                print(f"✓ Successfully deleted {file_count} backup files.")
                logger.info("Deleted %s backup files from %s", file_count, backup_dir)
            else:
                print("No backup files found to delete.")

        except OSError as e:
            logger.error("Error deleting backup files: %s", e)
            print(f"Error deleting backup files: {e}")

    def _delete_app_backups(self, global_config: GlobalConfigManager) -> None:
        """Delete backup files for a specific app."""
        backup_dir = global_config.expanded_app_backup_storage_path

        if not os.path.exists(backup_dir):
            print(f"Backup directory {backup_dir} does not exist.")
            return

        # Get list of apps that have backups
        apps = self._get_available_apps(backup_dir)

        if not apps:
            print("No app backups found.")
            return

        print("\nAvailable apps with backups:")
        for i, app in enumerate(apps, 1):
            print(f"{i}. {app}")

        try:
            app_choice = int(input(f"Select app number (1-{len(apps)}): "))
            if app_choice < 1 or app_choice > len(apps):
                print("Invalid selection.")
                return

            selected_app = apps[app_choice - 1]
            confirm = input(
                f"Are you sure you want to delete all backups for {selected_app}? (yes/no): "
            )
            if confirm.lower() != "yes":
                print("Operation cancelled.")
                return

            file_count = 0
            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                if not filename.lower().endswith(".appimage") or not os.path.isfile(filepath):
                    continue

                # Simple matching - check if filename starts with app name
                app_lower = selected_app.lower()
                filename_lower = filename.lower()

                if (
                    filename_lower.startswith(f"{app_lower}-")
                    or filename_lower.startswith(f"{app_lower}_")
                    or filename_lower == f"{app_lower}.appimage"
                ):
                    os.remove(filepath)
                    file_count += 1

            if file_count > 0:
                print(f"✓ Successfully deleted {file_count} backup files for {selected_app}.")
                logger.info("Deleted %s backup files for %s", file_count, selected_app)
            else:
                print(f"No backup files found for {selected_app}.")

        except ValueError:
            print("Invalid input. Please enter a number.")
        except OSError as e:
            logger.error("Error deleting app backups: %s", e)
            print(f"Error deleting app backups: {e!s}")

    def _delete_old_backups(self, global_config: GlobalConfigManager) -> None:
        """Delete backup files older than a specified date."""
        backup_dir = global_config.expanded_app_backup_storage_path

        if not os.path.exists(backup_dir):
            print(f"Backup directory {backup_dir} does not exist.")
            return

        print("\nDelete backups older than:")
        print("1. 1 week")
        print("2. 1 month")
        print("3. 3 months")
        print("4. 6 months")
        print("5. 1 year")
        print("6. Custom date (YYYY-MM-DD)")

        choice = input("Enter your choice (1-6): ")

        import datetime

        today = datetime.datetime.now()
        cutoff_date = None

        if choice == "1":
            cutoff_date = today - datetime.timedelta(days=7)
            date_desc = "1 week"
        elif choice == "2":
            cutoff_date = today - datetime.timedelta(days=30)
            date_desc = "1 month"
        elif choice == "3":
            cutoff_date = today - datetime.timedelta(days=90)
            date_desc = "3 months"
        elif choice == "4":
            cutoff_date = today - datetime.timedelta(days=180)
            date_desc = "6 months"
        elif choice == "5":
            cutoff_date = today - datetime.timedelta(days=365)
            date_desc = "1 year"
        elif choice == "6":
            date_str = input("Enter date (YYYY-MM-DD): ")
            try:
                cutoff_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                date_desc = date_str
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
                return
        else:
            print("Invalid choice.")
            return

        cutoff_timestamp = cutoff_date.timestamp()

        confirm = input(
            f"Are you sure you want to delete all backups older than {date_desc}? (yes/no): "
        )
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            return

        try:
            file_count = 0
            for filename in os.listdir(backup_dir):
                if filename.lower().endswith(".appimage"):
                    filepath = os.path.join(backup_dir, filename)
                    if os.path.isfile(filepath):
                        # Get file modification time
                        mod_time = os.path.getmtime(filepath)
                        if mod_time < cutoff_timestamp:
                            os.remove(filepath)
                            file_count += 1

            if file_count > 0:
                print(f"✓ Successfully deleted {file_count} backup files older than {date_desc}.")
                logger.info("Deleted %s backup files older than %s", file_count, date_desc)
            else:
                logger.info("No backup files found older than %s", date_desc)
                print(f"No backup files found older than {date_desc}.")

        except OSError as e:
            logger.error("Error deleting old backups: %s", e)
            print(f"Error deleting old backups: {e!s}")

    def _cleanup_to_max_backups(self, global_config: GlobalConfigManager) -> None:
        """Clean up backups to keep only max_backups per app."""
        backup_dir = global_config.expanded_app_backup_storage_path
        max_backups = global_config.max_backups

        if not os.path.exists(backup_dir):
            print(f"Backup directory {backup_dir} does not exist.")
            return

        print(f"This will keep only the {max_backups} most recent backups for each app.")
        confirm = input("Do you want to proceed? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            return

        apps = self._get_available_apps(backup_dir)
        if not apps:
            print("No app backups found.")
            return

        total_removed = 0

        for app in apps:
            app_backups = []

            # Find all backups for this app
            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                if not filename.lower().endswith(".appimage") or not os.path.isfile(filepath):
                    continue

                # Simple matching - check if filename starts with app name
                app_lower = app.lower()
                filename_lower = filename.lower()

                if (
                    filename_lower.startswith(f"{app_lower}-")
                    or filename_lower.startswith(f"{app_lower}_")
                    or filename_lower == f"{app_lower}.appimage"
                ):
                    mod_time = os.path.getmtime(filepath)
                    app_backups.append((filepath, mod_time, filename))

            # Sort backups by modification time (newest first)
            app_backups.sort(key=lambda x: x[1], reverse=True)

            len_app_backups = len(app_backups)
            # Log what we found
            logger.info("Found %s backups for %s, max_backups=%d", len_app_backups, app, max_backups)

            # Keep only the newest max_backups files
            if len_app_backups > max_backups:
                files_to_remove = app_backups[max_backups:]
                removed_count = 0
                for filepath, _, filename in files_to_remove:
                    try:
                        os.remove(filepath)
                        removed_count += 1
                        logger.info("Removed old backup: %s", filename)
                    except OSError as e:
                        logger.warning("Failed to remove old backup %s: %s", filename, e)

                total_removed += removed_count
                if removed_count > 0:
                    logger.info("Cleaned up %d old backups for %s", removed_count, app)

        if total_removed > 0:
            print(
                f"\n✓ Total: Removed {total_removed} backup files. Each app now has at most {max_backups} backups."
            )
        else:
            print(
                f"\nNo backups needed to be removed. All apps already have {max_backups} or fewer backups."
            )

    def _get_available_apps(self, backup_dir: str) -> list[str]:
        """Get a list of app names that have backups.

        Args:
            backup_dir: Path to backup directory

        Returns:
            list of unique app names extracted from backup filenames

        """
        apps = set()

        try:
            for filename in os.listdir(backup_dir):
                if filename.lower().endswith(".appimage"):
                    # Extract app name using simplified logic - get first part before "-" or "_"
                    filename_base = filename.split(".")[0]  # Remove extension

                    # Case 1: AppName-version-etc format
                    if "-" in filename_base:
                        app_name = filename_base.split("-")[0]
                    # Case 2: AppName_timestamp format
                    elif "_" in filename_base:
                        app_name = filename_base.split("_")[0]
                    # Case 3: Simple AppName format
                    else:
                        app_name = filename_base

                    apps.add(app_name)
        except OSError as e:
            logger.error("Error getting available apps: %s", e)

        return sorted(list(apps))
