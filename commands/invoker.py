import logging


class CommandInvoker:
    """Invoker to manage and execute commands."""

    def __init__(self):
        self.commands = {}

    def register_command(self, key, command):
        """Register a command with a specific key."""
        self.commands[key] = command

    def execute_command(self, key):
        """Execute a registered command."""
        command = self.commands.get(key)
        if command:
            command.execute()
        else:
            logging.error("Invalid choice. Please try again.")
