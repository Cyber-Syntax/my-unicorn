from commands.base import Command
from src.update import AppImageUpdater


class UpdateAllAppImagesCommand(Command):
    """Command to update all AppImages."""

    def execute(self):
        updater = AppImageUpdater()
        # listing json files, but those are on the class tough
        # selecting json files
        updater.update_all()
