from commands.base import Command
from src.global_config import GlobalConfigManager


class CreateGlobalConfigCommand(Command):
    """Command to create the global configuration file.

    This class is responsible for creating the global configuration file.
    It extends the Command class and implements the execute method to define
    the specific behavior of creating the global configuration file.
    """

    def execute(self):
        """Execute the command to create the global configuration file.

        This method initializes the GlobalConfigManager and calls the
        create_global_config method to create the global configuration file.
        """
        global_config = GlobalConfigManager()
        global_config.create_global_config()
