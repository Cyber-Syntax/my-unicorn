from my_unicorn.app_config import AppConfigManager
from my_unicorn.commands.base import Command


class CreateAppConfigCommand(Command):
    """Command to create an AppImage configuration file."""

    def execute(self):
        app_config = AppConfigManager()
        app_config.create_app_config()
