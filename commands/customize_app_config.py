from commands.base import Command
from src.app_config import AppConfigManager


class CustomizeAppConfigCommand(Command):
    """Command to customize the AppImage configuration file.

    This class is responsible for customizing the configuration file for an AppImage.
    It extends the Command class and implements the execute method to define
    the specific behavior of customizing the configuration file.
    """

    def execute(self):
        """Execute the command to customize the AppImage configuration file.

        This method initializes the AppConfigManager and calls the
        customize_appimage_config method to customize the configuration file.
        """
        app_config = AppConfigManager()
        app_config.customize_appimage_config()
