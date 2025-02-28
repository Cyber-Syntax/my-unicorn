from commands.base import Command
from src.app_config import AppConfigManager


class CustomizeAppConfigCommand(Command):
    """Command to create the global configuration file"""

    def execute(self):
        app_config = AppConfigManager
        app_config.customize_appimage_config()
