from commands.base import Command
from src.app_config import AppConfigManager


class CustomizeAppConfigCommand(Command):
    """Command to customize application configuration files"""

    def execute(self):
        """Execute the command to customize app configuration"""
        app_config = AppConfigManager()
        app_config.customize_appimage_config()
