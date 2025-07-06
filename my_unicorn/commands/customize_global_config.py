from my_unicorn.commands.base import Command
from my_unicorn.global_config import GlobalConfigManager


class CustomizeGlobalConfigCommand(Command):
    """Command to create the global configuration file"""

    def execute(self):
        global_config = GlobalConfigManager()
        global_config.customize_global_config()
