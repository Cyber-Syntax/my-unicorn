from commands.base import Command
from src.global_config import GlobalConfigManager


class CustomizeGlobalConfigCommand(Command):
    """Command to customize the global configuration file.

    This class is responsible for customizing the global configuration file.
    It extends the Command class and implements the execute method to define
    the specific behavior of customizing the global configuration file.
    """

    def execute(self):
        """Execute the command to customize the global configuration file.

        This method initializes the GlobalConfigManager and calls the
        customize_global_config method to customize the global configuration file.
        """
        global_config = GlobalConfigManager()
        global_config.customize_global_config()
