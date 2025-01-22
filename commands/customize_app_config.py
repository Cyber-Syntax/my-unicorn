from commands.base import Command
from src.app_config import AppConfigManager


class CustomizeAppConfigCommand(Command):
    """Command to customize the AppImage configuration file."""

    def execute(self):
        app_config = AppConfigManager()
        app_config.customize_app_config()
