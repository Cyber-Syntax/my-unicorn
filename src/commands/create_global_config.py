from src.commands.base import Command
from src.global_config import GlobalConfigManager


class CreateGlobalConfigCommand(Command):
    """Command to create the global configuration file"""

    def execute(self):
        global_config = GlobalConfigManager()
        global_config.create_global_config()
