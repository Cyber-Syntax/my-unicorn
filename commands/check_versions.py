# commands/check_versions.py
from commands.base import Command
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.update import AppImageUpdater


class CheckVersionsCommand(Command):
    """Command to check which AppImages need updates."""

    def __init__(self, global_config):
        self.global_config = global_config

    def execute(self):
        app_config = AppConfigManager()
        updater = AppImageUpdater(app_config, self.global_config)

        # Auto-select all files in batch mode
        selected_files = updater.select_files()
        if not selected_files:
            return None

        return updater.check_versions(selected_files)
