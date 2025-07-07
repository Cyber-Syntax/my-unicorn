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
            try:
                command.execute()
            except KeyboardInterrupt:
                logging.info("Command execution interrupted by user (Ctrl+C)")
                print("\nCommand interrupted. Returning to main menu...")
            except TypeError as e:
                logging.error("Type error occurred: %s", e)
                print(f"Error: {e}. Please check your configuration files.")
            except Exception as e:
                logging.error("Error executing command: %s", e)
                print(f"An error occurred: {e}")
        else:
            logging.error("Invalid choice. Please try again.")
            print("Invalid choice. Please try again.")
