from commands.base import Command
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.update import AppImageUpdater


class UpdateCommand(Command):
    """Command to update all outdated AppImages with batch mode support."""

    def execute(self):
        global_config = GlobalConfigManager()
        global_config.load_config()

        # Optionally, if you want to use CheckVersionsCommand, you can enable this:
        # check_cmd = CheckVersionsCommand(global_config)
        # outdated_apps = check_cmd.execute()

        app_config = AppConfigManager()
        updater = AppImageUpdater(app_config, global_config)

        # Auto-select all files in batch mode
        selected_files = updater.select_files()
        if not selected_files:
            return None

        # Instead of returning immediately, store the result
        outdated_apps = updater.check_versions(selected_files)

        # Now, proceed with the update logic
        if not outdated_apps:
            print("All AppImages are already up to date!")
            return

        # Handle confirmation based on batch mode
        if global_config.batch_mode:
            print("Batch mode: Automatically updating all outdated AppImages")
            self._perform_update(global_config, outdated_apps)
        else:
            self._show_confirmation_prompt(outdated_apps, global_config)

    def _show_confirmation_prompt(self, outdated_apps, global_config):
        """Show interactive confirmation prompt."""
        print("\nThe following AppImages will be updated:")
        for idx, app in enumerate(outdated_apps, 1):
            print(f"{idx}. {app['appimage_name']} (v{app['latest_version']})")

        confirm = (
            input("\nDo you want to proceed with updates? [y/N]: ").strip().lower()
        )
        if confirm == "y":
            self._perform_update(global_config, outdated_apps)
        else:
            print("Update cancelled.")

    def _perform_update(self, global_config, outdated_apps):
        """Execute the actual update process."""
        app_config = AppConfigManager()
        updater = AppImageUpdater(app_config, global_config)
        updater.update_selected_appimages(outdated_apps)
