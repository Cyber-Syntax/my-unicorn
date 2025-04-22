from src.commands.base import Command
from src.app_config import AppConfigManager


class CreateAppConfigCommand(Command):
    """Command to create an AppImage configuration file."""

    def execute(self):
        app_config = AppConfigManager()
        app_config.create_app_config()
