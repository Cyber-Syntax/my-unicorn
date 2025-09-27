"""Error classes for my-unicorn operations."""


class InstallationError(Exception):
    """Raised when installation fails."""

    def __init__(self, message: str, target: str | None = None) -> None:
        """Initialize installation error.

        Args:
            message: Error message
            target: Target that failed to install

        """
        super().__init__(message)
        self.target = target


class ValidationError(Exception):
    """Raised when target validation fails."""

    def __init__(self, message: str, target: str | None = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message
            target: Target that failed validation

        """
        super().__init__(message)
        self.target = target
