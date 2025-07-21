from typing import override

from my_unicorn.commands.base import Command
from my_unicorn.global_config import GlobalConfigManager


class CreateGlobalConfigCommand(Command):
    """Command to create the global configuration file"""

    @override
    def execute(self):
        global_config = GlobalConfigManager()
        global_config.create_global_config()
