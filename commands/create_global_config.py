from commands.base import Command
from src.global_config import GlobalConfigManager


class CreateAppConfigCommand(Command):
    """Command to create an AppImage configuration file."""

    def execute(self):
        global_config = GlobalConfigManager()
        global_config.create_global_config()
