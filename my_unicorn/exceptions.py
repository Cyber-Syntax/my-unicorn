"""Exception classes for my-unicorn operations."""


class InstallationError(Exception):
    """Raised when installation fails."""

    def __init__(self, message: str, target: str | None = None) -> None:
        """Initialize installation error.

        Args:
            message: Error message describing the installation failure.
            target: Optional name of the target that failed to install.

        """
        super().__init__(message)
        self.message = message
        self.target = target

    def __str__(self) -> str:
        """Return string representation of the error.

        Returns:
            Formatted error message with target if available.

        """
        if self.target:
            return f"Installation failed for '{self.target}': {self.message}"
        return f"Installation failed: {self.message}"


class ValidationError(Exception):
    """Raised when target validation fails."""

    def __init__(self, message: str, target: str | None = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message describing the validation failure.
            target: Optional name of the target that failed validation.

        """
        super().__init__(message)
        self.message = message
        self.target = target

    def __str__(self) -> str:
        """Return string representation of the error.

        Returns:
            Formatted error message with target if available.

        """
        if self.target:
            return f"Validation failed for '{self.target}': {self.message}"
        return f"Validation failed: {self.message}"
