"""Exception classes for my-unicorn operations."""


class MyUnicornError(Exception):
    """Base exception for my-unicorn operations."""

    error_prefix: str = "Operation failed"

    def __init__(self, message: str, target: str | None = None) -> None:
        """Initialize error with message and optional target.

        Args:
            message: Error message describing the failure.
            target: Optional name of the target that failed.

        """
        super().__init__(message)
        self.message = message
        self.target = target

    def __str__(self) -> str:
        """Return formatted error message."""
        if self.target:
            return f"{self.error_prefix} for '{self.target}': {self.message}"
        return f"{self.error_prefix}: {self.message}"


class InstallationError(MyUnicornError):
    """Raised when installation fails."""

    error_prefix = "Installation failed"


class ValidationError(MyUnicornError):
    """Raised when target validation fails."""

    error_prefix = "Validation failed"
