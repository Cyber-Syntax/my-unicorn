from my_unicorn.app_config import AppConfigManager
from my_unicorn.commands.base import Command


class CustomizeAppConfigCommand(Command):
    """Command to customize application configuration files"""

    def execute(self):
        """Execute the command to customize app configuration"""
        app_config = AppConfigManager()
        app_config.customize_appimage_config()
