"""Domain-specific exception classes for my-unicorn operations.

This module defines a hierarchical exception structure that provides:
- Consistent error handling patterns across the codebase
- Rich context data for debugging and logging
- Retry metadata for network-related errors
- Exception chaining support for preserving root causes
"""

from __future__ import annotations


class MyUnicornError(Exception):
    """Base exception for all my-unicorn errors.

    Provides a consistent interface for error handling with support for:
    - Human-readable messages
    - Contextual data (app_name, version, file_path, etc.)
    - Retry logic metadata
    - Exception chaining

    Attributes:
        message: Human-readable error message.
        target: Optional target name (for backward compatibility).
        context: Additional context data for debugging.
        is_retryable: Whether this error can be retried.
        retry_after: Suggested retry delay in seconds (None = immediate).
        error_prefix: Prefix for string representation.

    Example:
        >>> try:
        ...     raise MyUnicornError("Download failed", context={"url": "https://..."})
        ... except MyUnicornError as e:
        ...     if e.is_retryable:
        ...         time.sleep(e.retry_after or 1)
        ...         # Retry logic

    """

    error_prefix: str = "Operation failed"

    def __init__(  # noqa: PLR0913
        self,
        message: str,
        target: str | None = None,
        *,
        context: dict[str, object] | None = None,
        is_retryable: bool = False,
        retry_after: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize error with message and optional metadata.

        Args:
            message: Error message describing the failure.
            target: Optional name of the target that failed.
            context: Additional context data (app_name, version, etc.).
            is_retryable: Whether this error can be retried.
            retry_after: Suggested retry delay in seconds.
            cause: Original exception that caused this error.

        """
        super().__init__(message)
        self.message = message
        self.target = target
        self.context = context or {}
        self.is_retryable = is_retryable
        self.retry_after = retry_after

        if cause:
            self.__cause__ = cause

    def __str__(self) -> str:
        """Return formatted error message with context."""
        if self.target:
            base = f"{self.error_prefix} for '{self.target}': {self.message}"
        else:
            base = f"{self.error_prefix}: {self.message}"

        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base += f" ({ctx_str})"
        return base


class InstallationError(MyUnicornError):
    """Raised when installation fails."""

    error_prefix = "Installation failed"


class ValidationError(MyUnicornError):
    """Raised when target validation fails."""

    error_prefix = "Validation failed"


# =============================================================================
# Verification Exceptions
# =============================================================================


class VerificationError(MyUnicornError):
    """Base class for verification errors.

    Verification errors occur when hash verification fails during
    download validation. These are typically non-retryable since they
    indicate data integrity issues.

    Example:
        >>> try:
        ...     await verify_download(file_path, expected_hash)
        ... except VerificationError as e:
        ...     logger.error("Verification failed: %s", e.context)

    """

    error_prefix = "Verification failed"


class HashMismatchError(VerificationError):
    """Raised when computed hash doesn't match expected hash.

    This error indicates a potential data corruption or tampering.
    Re-downloading may help if the original download was corrupted.

    Attributes:
        expected: Expected hash value.
        actual: Computed hash value.
        algorithm: Hash algorithm used (sha256, sha512).
        file_path: Path to the file that was verified.

    """

    def __init__(
        self,
        expected: str,
        actual: str,
        algorithm: str,
        file_path: str,
    ) -> None:
        """Initialize hash mismatch error with verification details.

        Args:
            expected: Expected hash value from release.
            actual: Computed hash value from file.
            algorithm: Hash algorithm used (sha256, sha512).
            file_path: Path to the file that was verified.

        """
        super().__init__(
            f"Hash verification failed for {file_path}",
            context={
                "expected_hash": expected,
                "actual_hash": actual,
                "algorithm": algorithm,
                "file_path": file_path,
            },
            is_retryable=False,
        )
        self.expected = expected
        self.actual = actual
        self.algorithm = algorithm
        self.file_path = file_path


class HashUnavailableError(VerificationError):
    """Raised when no hash is available for verification.

    This can occur when the release doesn't provide checksum files
    or the checksum format is not supported.

    Attributes:
        app_name: Name of the application.
        version: Version being verified.

    """

    def __init__(self, app_name: str, version: str) -> None:
        """Initialize hash unavailable error.

        Args:
            app_name: Name of the application.
            version: Version being verified.

        """
        super().__init__(
            f"No hash available for {app_name} v{version}",
            context={"app_name": app_name, "version": version},
            is_retryable=False,
        )
        self.app_name = app_name
        self.version = version


class HashComputationError(VerificationError):
    """Raised when hash computation fails (I/O error, algorithm error).

    This is typically retryable since the underlying cause may be
    transient (file system busy, temporary I/O error).

    Attributes:
        file_path: Path to the file being hashed.
        algorithm: Hash algorithm being used.

    """

    def __init__(
        self,
        file_path: str,
        algorithm: str,
        cause: Exception,
    ) -> None:
        """Initialize hash computation error.

        Args:
            file_path: Path to the file being hashed.
            algorithm: Hash algorithm being used.
            cause: Original exception that caused the failure.

        """
        super().__init__(
            f"Failed to compute {algorithm} hash for {file_path}",
            context={"file_path": file_path, "algorithm": algorithm},
            is_retryable=True,
            retry_after=1,
            cause=cause,
        )
        self.file_path = file_path
        self.algorithm = algorithm


# =============================================================================
# Workflow Exceptions
# =============================================================================


class WorkflowError(MyUnicornError):
    """Base class for workflow orchestration errors.

    Workflow errors occur during high-level operations like install,
    update, or remove. They typically wrap lower-level exceptions
    with additional context about the operation being performed.

    """

    error_prefix = "Workflow failed"


class InstallError(WorkflowError):
    """Raised when installation workflow fails.

    This wraps errors that occur during the install process,
    including download, verification, and post-processing steps.

    """

    error_prefix = "Install failed"


class UpdateError(WorkflowError):
    """Raised when update workflow fails.

    This wraps errors that occur during the update process,
    including version checking, download, and replacement steps.

    """

    error_prefix = "Update failed"


class PostProcessingError(WorkflowError):
    """Raised when post-download processing fails.

    Post-processing includes icon extraction, desktop entry creation,
    and permission setting. These errors are typically non-fatal.

    Attributes:
        step: Name of the processing step that failed.
        app_name: Name of the application being processed.

    """

    error_prefix = "Post-processing failed"

    def __init__(
        self,
        step: str,
        app_name: str,
        cause: Exception,
    ) -> None:
        """Initialize post-processing error.

        Args:
            step: Name of the processing step (icon_extraction, desktop_entry).
            app_name: Name of the application being processed.
            cause: Original exception that caused the failure.

        """
        super().__init__(
            f"Post-processing step '{step}' failed for {app_name}",
            context={"step": step, "app_name": app_name},
            is_retryable=False,
            cause=cause,
        )
        self.step = step
        self.app_name = app_name


# =============================================================================
# Network Exceptions
# =============================================================================


class NetworkError(MyUnicornError):
    """Base class for network-related errors.

    Network errors are typically retryable since they may be caused
    by transient issues like network congestion or server load.

    Attributes:
        url: URL that caused the error (if applicable).
        status_code: HTTP status code (if applicable).

    """

    error_prefix = "Network error"

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status_code: int | None = None,
        retry_after: int = 5,
        cause: Exception | None = None,
    ) -> None:
        """Initialize network error with connection details.

        Args:
            message: Error message describing the failure.
            url: URL that caused the error.
            status_code: HTTP status code if applicable.
            retry_after: Suggested retry delay in seconds.
            cause: Original exception that caused the failure.

        """
        context: dict[str, object] = {}
        if url:
            context["url"] = url
        if status_code:
            context["status_code"] = status_code

        super().__init__(
            message,
            context=context,
            is_retryable=True,
            retry_after=retry_after,
            cause=cause,
        )
        self.url = url
        self.status_code = status_code


class DownloadError(NetworkError):
    """Raised when file download fails.

    This can occur due to network issues, server errors, or
    file not found (404) responses.

    """

    error_prefix = "Download failed"


class GitHubAPIError(NetworkError):
    """Raised when GitHub API request fails.

    This includes rate limiting, authentication failures,
    and API endpoint errors.

    """

    error_prefix = "GitHub API error"


# =============================================================================
# Configuration Exceptions
# =============================================================================


class ConfigurationError(MyUnicornError):
    """Raised when configuration is invalid or missing.

    Configuration errors are not retryable since they require
    user intervention to fix the configuration.

    Attributes:
        config_path: Path to the configuration file.
        field: Specific field that caused the error.

    """

    error_prefix = "Configuration error"

    def __init__(
        self,
        message: str,
        *,
        config_path: str | None = None,
        field: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize configuration error.

        Args:
            message: Error message describing the configuration issue.
            config_path: Path to the configuration file.
            field: Specific field that caused the error.
            cause: Original exception that caused the failure.

        """
        context: dict[str, object] = {}
        if config_path:
            context["config_path"] = config_path
        if field:
            context["field"] = field

        super().__init__(
            message,
            context=context,
            is_retryable=False,
            cause=cause,
        )
        self.config_path = config_path
        self.field = field


# =============================================================================
# Locking Exceptions
# =============================================================================


class LockError(MyUnicornError):
    """Raised when lock acquisition fails.

    Lock errors occur when the application attempts to acquire a process-level
    lock but fails, typically because another instance is already running.

    Example:
        >>> try:
        ...     async with LockManager(lock_path):
        ...         pass
        ... except LockError as e:
        ...     logger.error("Cannot acquire lock: %s", e.message)

    """

    error_prefix = "Lock acquisition failed"
