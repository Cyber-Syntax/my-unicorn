class Command:
    """Abstract base class for all commands."""

    def execute(self):
        raise NotImplementedError("Subclasses must implement the 'execute' method.")
