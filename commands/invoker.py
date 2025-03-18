class CommandInvoker:
    """Invoker to manage and execute commands.

    This class is responsible for managing and executing commands.
    It maintains a registry of commands and provides methods to
    register and execute them.
    """

    def __init__(self):
        self.commands = {}

    def register_command(self, key, command):
        """Register a command with a specific key.

        Args:
            key (int): The key to associate with the command.
            command (Command): The command to register.
        """
        self.commands[key] = command

    def execute_command(self, key):
        """Execute a registered command.

        Args:
            key (int): The key associated with the command to execute.

        Raises:
            KeyError: If the key is not found in the registered commands.
        """
        command = self.commands.get(key)
        if command:
            command.execute()
        else:
            print("Invalid choice. Please try again.")
