from commands.base import Command
from src.global_config import GlobalConfigManager


class CustomizeGlobalConfigCommand(Command):
    """Command to customize the global configuration."""

    def execute(self):
        global_config = GlobalConfigManager()
        global_config.load_config()
        global_config.customize_global_config()
