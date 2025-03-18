class Command:
    """Abstract base class for all commands.

    This class serves as a blueprint for creating specific command classes.
    Each command class that inherits from this base class must implement the
    `execute` method to define the specific behavior of the command.
    """

    def execute(self):
        """Execute the command.

        This method should be overridden by subclasses to provide the specific
        implementation of the command's behavior.
        """
        raise NotImplementedError("Subclasses must implement the 'execute' method.")
