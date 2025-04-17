#!/usr/bin/env python3
import logging
import os
import shutil
from typing import Dict, List, Optional, Tuple

from src.commands.command import Command
from src.global_config import GlobalConfigManager


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
        backup_dir = global_config.expanded_appimage_download_backup_folder_path

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
                logging.info(f"Deleted {file_count} backup files from {backup_dir}")
            else:
                print("No backup files found to delete.")

        except OSError as e:
            logging.error(f"Error deleting backup files: {str(e)}")
            print(f"Error deleting backup files: {str(e)}")

    def _delete_app_backups(self, global_config: GlobalConfigManager) -> None:
        """Delete backup files for a specific app."""
        backup_dir = global_config.expanded_appimage_download_backup_folder_path

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
                if filename.lower().startswith(
                    f"{selected_app.lower()}_"
                ) and filename.lower().endswith(".appimage"):
                    filepath = os.path.join(backup_dir, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        file_count += 1

            if file_count > 0:
                print(f"✓ Successfully deleted {file_count} backup files for {selected_app}.")
                logging.info(f"Deleted {file_count} backup files for {selected_app}")
            else:
                print(f"No backup files found for {selected_app}.")

        except ValueError:
            print("Invalid input. Please enter a number.")
        except OSError as e:
            logging.error(f"Error deleting app backups: {str(e)}")
            print(f"Error deleting app backups: {str(e)}")

    def _delete_old_backups(self, global_config: GlobalConfigManager) -> None:
        """Delete backup files older than a specified date."""
        backup_dir = global_config.expanded_appimage_download_backup_folder_path

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
                logging.info(f"Deleted {file_count} backup files older than {date_desc}")
            else:
                print(f"No backup files found older than {date_desc}.")

        except OSError as e:
            logging.error(f"Error deleting old backups: {str(e)}")
            print(f"Error deleting old backups: {str(e)}")

    def _cleanup_to_max_backups(self, global_config: GlobalConfigManager) -> None:
        """Clean up backups to keep only max_backups per app."""
        backup_dir = global_config.expanded_appimage_download_backup_folder_path
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
            for filename in os.listdir(backup_dir):
                if filename.lower().startswith(f"{app.lower()}_") and filename.lower().endswith(
                    ".appimage"
                ):
                    filepath = os.path.join(backup_dir, filename)
                    if os.path.isfile(filepath):
                        mod_time = os.path.getmtime(filepath)
                        app_backups.append((filepath, mod_time))

            # Sort backups by modification time (newest first)
            app_backups.sort(key=lambda x: x[1], reverse=True)

            # Keep only the newest max_backups files
            files_to_remove = app_backups[max_backups:]
            if files_to_remove:
                removed_count = 0
                for filepath, _ in files_to_remove:
                    try:
                        os.remove(filepath)
                        removed_count += 1
                        logging.info(f"Removed old backup: {os.path.basename(filepath)}")
                    except OSError as e:
                        logging.warning(f"Failed to remove old backup {filepath}: {e}")

                total_removed += removed_count
                if removed_count > 0:
                    print(f"✓ Cleaned up {removed_count} old backup(s) for {app}")
                    logging.info(f"Cleaned up {removed_count} old backups for {app}")

        if total_removed > 0:
            print(
                f"\n✓ Total: Removed {total_removed} backup files. Each app now has at most {max_backups} backups."
            )
        else:
            print(
                f"\nNo backups needed to be removed. All apps already have {max_backups} or fewer backups."
            )

    def _get_available_apps(self, backup_dir: str) -> List[str]:
        """
        Get a list of app names that have backups.

        Args:
            backup_dir: Path to backup directory

        Returns:
            List of unique app names extracted from backup filenames
        """
        apps = set()

        try:
            for filename in os.listdir(backup_dir):
                if filename.lower().endswith(".appimage") and "_" in filename:
                    # Extract app name before the underscore
                    app_name = filename.split("_")[0]
                    apps.add(app_name)
        except OSError as e:
            logging.error(f"Error getting available apps: {str(e)}")

        return sorted(list(apps))
