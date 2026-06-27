"""Domain-specific exception classes for my-unicorn operations.

This module defines a hierarchical exception structure that provides:
- Consistent error handling patterns across the codebase
- Rich context data for debugging and logging
- Retry metadata for network-related errors
- Exception chaining support for preserving root causes

ErrorCode                <-- stable identifiers
        │
        ▼
ERRORS / ERROR_MESSAGES  <-- centralized human messages
        │
        ▼
MyUnicornError           <-- stores code, context, cause
        │
        ├── InstallError
        ├── VerificationError
        ├── NetworkError
        ├── ConfigurationError
        └── UpdateError
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# NOTE: currently our usage is simple
# use errorcode for exact error
# and use message for details
# use general if you don't know exact error
# use exact error from ErrorCode if you now exact error
class ErrorCode(Enum):
    """Error codes for progress tracking."""

    GITHUB_API_ERROR = "github_api_eror"
    DOWNLOAD_FAILED = "download_failed"
    PROCESSING_FAILED = "processing_failed"
    VERIFICATION_FAILED = "verification_failed"
    INSTALLATION_FAILED = "installation_failed"
    UPDATE_FAILED = "update_failed"
    ICON_EXTRACTION_FAILED = "icon_extraction_failed"
    DESKTOP_ENTRY_CREATION_FAILED = "desktop_entry_creation_failed"
    APPIMAGE_MOVE_FAILED = "appimage_move_failed"
    UNKNOWN_ERROR = "unknown_error"
    APPIMAGE_ASSET_NOT_FOUND = "appimage_asset_not_found"
    CHECKSUM_ASSET_NOT_FOUND = "checksum_asset_not_found"
    DIGEST_HASH_NOT_FOUND = "digest_hash_not_found"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_DNS_FAILURE = "network_dns_failure"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    PERMISSION_DENIED = "permission_denied"
    LOCK_INSTANCE_FAILED = "lock_instance_failed"
    LOCK_ACQUIRE_FAILED = "lock_acquire_failed"


# TODO: add missing errorcodes from above
ERROR_MESSAGES = {
    ErrorCode.DOWNLOAD_FAILED: "Something went wrong while downloading",
    ErrorCode.APPIMAGE_ASSET_NOT_FOUND: "appimage asset not found : appimage builds may still be processing, try again later. Some developers may not provide appimage builds, so this might be external to my-unicorn's control.",
    ErrorCode.NETWORK_TIMEOUT: "network timeout while downloading asset",
    ErrorCode.NETWORK_DNS_FAILURE: "could not resolve upstream host",
    ErrorCode.DESKTOP_ENTRY_CREATION_FAILED: "Failed to create desktop entry",
    ErrorCode.PERMISSION_DENIED: "permission denied",
    ErrorCode.CHECKSUM_MISMATCH: "checksum verification failed because of hash mismatches",
    ErrorCode.UNKNOWN_ERROR: "an unknown error occurred",
    ErrorCode.LOCK_INSTANCE_FAILED: "Another my-unicorn instance is already running.Please wait or stop the other instance.",
    ErrorCode.LOCK_ACQUIRE_FAILED: "Failed to acquire lock",
}


class WarningCode(Enum):
    """Warning codes for progress tracking."""

    NO_CHECKSUM_SKIPPED = "no_checksum_skipped"
    NO_CHECKSUM_UNSUPPORTED = "no_checksum_unsupported"


WARNING_MESSAGES = {
    WarningCode.NO_CHECKSUM_SKIPPED: "no checksum provided by upstream : skipping verification",
    WarningCode.NO_CHECKSUM_UNSUPPORTED: "checksum asset not found : some developers not provide any, please report an issue for the app maintainers if you verified this isn't my-unicorn fault",
}


# TODO: we didn't implement any special case for
# display state and for YAGNI
# we probably going to remove this
# keep it for now, remove later
class ErrorDisplayState(Enum):
    """Display state for errors in progress tracking."""

    PENDING = "PENDING"
    SHOWN = "SHOWN"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class ErrorSeverity(Enum):
    """Error severity levels for progress tracking."""

    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ErrorContext:
    """Context for errors in progress tracking."""

    phase: str
    app_name: str
    error_code: ErrorCode
    error_severity: ErrorSeverity
    details: str | None


@dataclass
class TaskError(ErrorContext):
    """Context for errors specific to a task in progress tracking."""

    processing_phase: str
    timestamp: str


# -- exceptions
# Main exception for my-unicorn
# TODO: make sure it support ErrorCode and messages
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
        message: str | None = None,
        target: str | None = None,
        *,
        error_code: ErrorCode | None = None,
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
        self.error_code = error_code

        if message is None and error_code is not None:
            message = ERROR_MESSAGES.get(
                error_code,
                ERROR_MESSAGES[ErrorCode.UNKNOWN_ERROR],
            )

        if message is None:
            message = "Unknown error"

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


# TODO: remove this and use InstallError instead
class InstallationError(MyUnicornError):
    """Raised when installation fails."""

    error_prefix = "Installation failed"


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


class InstallError(MyUnicornError):
    """Raised when installation workflow fails.

    This wraps errors that occur during the install process,
    including download, verification, and post-processing steps.

    """

    error_prefix = "Install failed"


class UpdateError(MyUnicornError):
    """Raised when update workflow fails.

    This wraps errors that occur during the update process,
    including version checking, download, and replacement steps.

    """

    error_prefix = "Update failed"


# TODO: this is used from logger, update modules
# might be better to add a message in above messages section
# and remove this instead for easy showcase
# but not sure about how we canhandle context?
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


# TODO: same like above configuration exception
# we use it in runner.py for loc error
# better to use message via ErrorCode
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
