from commands.base import Command
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager


class CreateAppConfigCommand(Command):
    """Command to create an AppImage configuration file.

    This class is responsible for creating a configuration file for an AppImage.
    It extends the Command class and implements the execute method to define
    the specific behavior of creating the configuration file.
    """

    def execute(self):
        """Execute the command to create an AppImage configuration file.

        This method initializes the AppConfigManager and GlobalConfigManager,
        and calls the create_app_config method to create the configuration file.
        """
        app_config = AppConfigManager()
        global_config = GlobalConfigManager()
        self.create_config(app_config, global_config)

    def create_config(self, app_config, global_config):
        """Create the configuration file for the AppImage.

        This method combines the common functionality of creating the configuration
        file from both AppConfigManager and GlobalConfigManager.
        """
        app_config.create_app_config()
        global_config.create_global_config()
