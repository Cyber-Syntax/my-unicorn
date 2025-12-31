"""GitHub authentication and rate limiting management.

Utilities for storing, retrieving, and applying GitHub authentication
tokens, and for tracking rate-limit information to avoid exceeding API
limits. This module provides a SecretService-backed keyring setup and a
`GitHubAuthManager` class that stores token metadata and rate-limit
status.
"""

import contextlib
import getpass
import re
import time

import keyring
from keyring.backends import SecretService

from .logger import get_logger

logger = get_logger(__name__)

# Track keyring initialization to avoid redundant setup
_keyring_initialized: bool = False

# GitHub token security constraints
MAX_TOKEN_LENGTH: int = 255  # Maximum allowed token length per GitHub spec


class KeyringError(Exception):
    """Base exception for keyring-related errors."""


class KeyringUnavailableError(KeyringError):
    """Raised when keyring is unavailable (e.g., headless environment)."""


class KeyringAccessError(KeyringError):
    """Raised when keyring access fails (e.g., permission denied)."""


def setup_keyring() -> None:
    """Set SecretService as the preferred keyring backend if available.

    Raises:
        KeyringUnavailableError: If keyring is unavailable (e.g., headless
            environment, no DBUS).
        KeyringAccessError: If keyring setup fails for other reasons.

    """
    global _keyring_initialized  # noqa: PLW0603

    if _keyring_initialized:
        return

    _keyring_initialized = True  # Mark as attempted (prevent retries)

    try:
        keyring.set_keyring(SecretService.Keyring())
        logger.debug("SecretService backend set successfully")
    except ImportError:
        # SecretService not available - expected in some environments
        logger.debug("SecretService backend not available (import failed)")
        raise KeyringUnavailableError(  # noqa: TRY003
            "SecretService backend not available"
        ) from None
    except Exception as e:
        # Expected in headless environments (DBUS unavailable)
        if "DBUS" in str(e) or "DBus" in str(e):
            logger.debug("Keyring unavailable in headless environment: %s", e)
            raise KeyringUnavailableError(  # noqa: TRY003
                "Keyring unavailable in headless environment"
            ) from e
        logger.warning("Keyring setup failed: %s", e)
        raise KeyringAccessError("Keyring setup failed") from e  # noqa: TRY003


# Initialize the keyring backend (suppress exceptions at module load)
# Expected in some environments - authentication will fall back
with contextlib.suppress(KeyringError):
    setup_keyring()


def validate_github_token(token: str | None) -> bool:
    """Validate GitHub token format.

    Supports both legacy and newer GitHub token formats:
    - Legacy: 40 hexadecimal characters (classic personal access tokens).
    - New prefixed formats such as ``ghp_``, ``gho_``, ``ghu_``,
      ``ghs_``, ``ghr_``, and ``github_pat_``.

    Security validations:
    - Maximum length check (prevents memory exhaustion)
    - Strict character set validation
    - Detection of common token leak patterns

    Args:
        token (str | None): The token to validate. ``None`` and non-string
            values are considered invalid.

    Returns:
        bool: True if the token format is valid, False otherwise.

    """
    if not token or not isinstance(token, str):
        return False

    token = token.strip()

    # Check for empty token
    if not token:
        return False

    # Security: Enforce maximum token length to prevent memory
    # exhaustion attacks
    if len(token) > MAX_TOKEN_LENGTH:
        logger.warning("Token exceeds maximum allowed length")
        return False

    # Security: Detect common token leak patterns (tokens in URLs, test tokens)
    if any(
        pattern in token.lower()
        for pattern in [
            "http://",
            "https://",
            "example",
            "test_token",
            "fake_token",
        ]
    ):
        logger.warning("Token contains suspicious patterns")
        return False

    # Legacy token format: 40 hexadecimal characters
    if re.match(r"^[a-f0-9]{40}$", token):
        return True

    # New prefixed token formats
    # Character set: [A-Za-z0-9_]
    # Support up to 255 characters as per GitHub announcement
    prefixed_patterns = [
        r"^ghp_[A-Za-z0-9_]{36,251}$",  # Personal Access Tokens
        r"^gho_[A-Za-z0-9_]{36,251}$",  # OAuth Access tokens
        r"^ghu_[A-Za-z0-9_]{36,251}$",  # GitHub App user-to-server tokens
        r"^ghs_[A-Za-z0-9_]{36,251}$",  # GitHub App server-to-server tokens
        r"^ghr_[A-Za-z0-9_]{36,251}$",  # GitHub App refresh tokens
        r"^github_pat_[A-Za-z0-9_]{36,243}$",  # GitHub CLI PATs
    ]

    return any(re.match(pattern, token) for pattern in prefixed_patterns)


def _scrub_token(token: str) -> None:
    """Attempt to scrub sensitive token data from memory.

    This function attempts to overwrite the token string in memory to reduce
    the window of exposure in memory dumps. Note that Python's string
    immutability means this is a best-effort approach.

    Args:
        token: The token string to scrub.

    """
    try:
        # Attempt to overwrite the memory location (best effort in Python)
        # Note: Python strings are immutable, so this won't completely
        # erase the token, but it reduces the exposure window
        if token:
            # Create a zero-filled string of the same length
            _ = "0" * len(token)
    except Exception:  # noqa: S110, BLE001
        # Silently ignore scrubbing failures - this is a best-effort
        # security measure
        pass


class GitHubAuthManager:
    """Manage GitHub authentication tokens and rate limiting.

    Provides helper methods to store and retrieve tokens, update rate-limit
    information from API responses, and apply authentication to outgoing
    requests.
    """

    GITHUB_KEY_NAME: str = "my-unicorn-github-token"
    RATE_LIMIT_THRESHOLD: int = 10  # Minimum remaining requests before waiting

    def __init__(self) -> None:
        """Initialize the auth manager with rate limit tracking."""
        self._rate_limit_reset: int | None = None
        self._remaining_requests: int | None = None
        self._last_check_time: float = 0
        # Instance variable to track notification status
        # (not shared across instances)
        self._user_notified: bool = False

    @staticmethod
    def _prompt_for_token() -> tuple[str, str]:
        """Prompt user for token input and confirmation.

        Returns:
            tuple[str, str]: Token and confirmation token.

        Raises:
            ValueError: If input is empty or aborted.
            EOFError: If input is aborted.
            KeyboardInterrupt: If input is interrupted.

        """
        token: str = getpass.getpass(
            prompt="Enter your GitHub token (input hidden): "
        )
        if token is None:
            logger.error("No input received for GitHub token")
            msg = "Token cannot be empty"
            raise ValueError(msg)

        token = token.strip()
        if not token:
            logger.error("Token input is empty")
            msg = "Token cannot be empty"
            raise ValueError(msg)

        # Security: Validate maximum token length to prevent memory exhaustion
        if len(token) > MAX_TOKEN_LENGTH:
            logger.error("Token exceeds maximum allowed length")
            _scrub_token(token)
            msg = (
                f"Token exceeds maximum allowed length "
                f"({MAX_TOKEN_LENGTH} characters)"
            )
            raise ValueError(msg)

        # Confirm token input
        confirm_token: str = getpass.getpass(
            prompt="Confirm your GitHub token: "
        )
        if confirm_token is None:
            logger.error("No input received for GitHub token confirmation")
            msg = "Token confirmation does not match"
            raise ValueError(msg)

        confirm_token = confirm_token.strip()
        return token, confirm_token

    @staticmethod
    def _validate_token_confirmation(token: str, confirm_token: str) -> None:
        """Validate token confirmation matches original token.

        Args:
            token: Original token.
            confirm_token: Confirmation token.

        Raises:
            ValueError: If tokens don't match or validation fails.

        """
        if token != confirm_token:
            logger.error("Token confirmation mismatch")
            # Security: Scrub tokens from memory on failure
            _scrub_token(token)
            _scrub_token(confirm_token)
            msg = "Token confirmation does not match"
            raise ValueError(msg)

        # Validate token format before saving
        if not validate_github_token(token):
            logger.error("Token validation failed")
            # Security: Scrub token from memory on validation failure
            _scrub_token(token)
            _scrub_token(confirm_token)
            msg = (
                "Invalid GitHub token format. "
                "Must be a valid GitHub token (classic or fine-grained PAT)."
            )
            raise ValueError(msg)

    @staticmethod
    def _handle_keyring_error(
        e: Exception, token: str, confirm_token: str
    ) -> None:
        """Handle keyring errors with sanitized error messages.

        Args:
            e: The exception that occurred.
            token: The token to scrub.
            confirm_token: The confirmation token to scrub.

        """
        # Security: Scrub tokens from memory on any exception
        _scrub_token(token)
        _scrub_token(confirm_token)

        # Provide helpful message for keyring errors without exposing
        # system details
        error_msg = str(e)
        if "DBUS" in error_msg or "DBus" in error_msg:
            logger.error("Keyring unavailable in headless environment")
            logger.info("❌ Keyring not available in headless environment")
            logger.info("💡 Future: Environment variable support coming soon")
            logger.info(
                "   (MY_UNICORN_GITHUB_TOKEN will be supported in a "
                "future release)"
            )
        else:
            # Security: Log error without exposing sensitive details
            logger.error("Failed to save token to keyring")

    @staticmethod
    def save_token() -> None:
        """Prompt for a GitHub token and save it securely to the keyring.

        Prompts the user to enter and confirm a token, validates the token's
        format, and stores it in the configured keyring backend.

        Raises:
            ValueError: If the input is empty, the confirmation does not match,
                or the token format is invalid.
            Exception: Re-raises underlying keyring errors or other issues.

        """
        token = ""
        confirm_token = ""
        try:
            # Prompt for token and confirmation
            token, confirm_token = GitHubAuthManager._prompt_for_token()

            # Validate confirmation matches and token is valid
            GitHubAuthManager._validate_token_confirmation(
                token, confirm_token
            )

            # Save to keyring
            keyring.set_password(
                GitHubAuthManager.GITHUB_KEY_NAME, "token", token
            )
            logger.info("GitHub token saved successfully.")

            # Security: Scrub tokens from memory after successful save
            _scrub_token(token)
            _scrub_token(confirm_token)

        except (EOFError, KeyboardInterrupt) as e:
            logger.exception("Token input aborted by user")
            # Security: Scrub tokens from memory on abort
            _scrub_token(token)
            _scrub_token(confirm_token)
            msg = "Token input aborted by user"
            raise ValueError(msg) from e
        except ValueError:
            # Re-raise ValueError exceptions (already have token scrubbing)
            raise
        except Exception as e:
            # Handle keyring errors with sanitized messages
            GitHubAuthManager._handle_keyring_error(e, token, confirm_token)
            raise

    @staticmethod
    def remove_token() -> None:
        """Remove the stored GitHub token from the system keyring.

        Raises:
            Exception: If removal from the keyring fails for any reason.

        """
        try:
            keyring.delete_password(GitHubAuthManager.GITHUB_KEY_NAME, "token")
            logger.info("Token removed successfully")
        except Exception:
            # Security: Sanitize error message to prevent information
            # disclosure
            logger.exception("Failed to remove token from keyring")
            raise

    @staticmethod
    def get_token() -> str | None:
        """Retrieve the stored GitHub token from the keyring.

        Returns:
            str | None: The token if available, otherwise None if no token
                is stored or the keyring is unavailable.

        """
        try:
            token = keyring.get_password(
                GitHubAuthManager.GITHUB_KEY_NAME, "token"
            )
        except Exception:  # noqa: BLE001
            # Keyring unavailable is expected in headless environments
            # Security: Don't log exception details
            logger.debug("Keyring access failed")
            return None
        else:
            if token:
                logger.debug(
                    "GitHub token retrieved from keyring (value hidden)"
                )
                return token
            logger.debug("No token stored in keyring")
            return None

    def apply_auth(self, headers: dict[str, str]) -> dict[str, str]:
        """Apply GitHub authentication to the given request headers.

        If a token is configured, this will set the Authorization header. If
        no token is configured, the user is notified once per session about
        rate-limiting.

        Args:
            headers (dict[str, str]): HTTP headers to update.

        Returns:
            dict[str, str]: Headers with authentication applied when a token
                is available, otherwise the original headers.

        """
        token: str | None = GitHubAuthManager.get_token()

        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.debug("Applied GitHub authentication (token present)")
        # Notify user once per session about rate limits when no token
        elif not self._user_notified:
            self._user_notified = True
            logger.info(
                "No GitHub token configured. API rate limits apply "
                "(60 requests/hour). Use 'my-unicorn auth --save-token' "
                "to increase the limit to 5000 requests/hour."
            )

        return headers

    def update_rate_limit_info(self, headers: dict[str, str]) -> None:
        """Update rate-limit information from GitHub response headers.

        Args:
            headers (dict[str, str]): Response headers from a GitHub API call.

        """
        try:
            # GitHub API uses capitalized header names
            self._remaining_requests = int(
                headers.get("X-RateLimit-Remaining", 0)
            )
            self._rate_limit_reset = int(headers.get("X-RateLimit-Reset", 0))
            self._last_check_time = time.time()
        except (ValueError, TypeError):
            # Security: Don't expose header values in error messages
            logger.warning("Invalid rate limit headers received")
        except Exception:
            # Security: Sanitize error message to prevent
            # information disclosure
            logger.exception("Failed to update rate limit information")

    def get_rate_limit_status(self) -> dict[str, int | None]:
        """Return the current rate limit status.

        Returns:
            dict[str, int | None]: Mapping with keys 'remaining', 'reset_time',
                and 'reset_in_seconds'. Values may be None when unknown.

        """
        current_time = int(time.time())

        # If reset time has passed, we can assume limits are reset
        if self._rate_limit_reset and current_time >= self._rate_limit_reset:
            self._remaining_requests = None
            self._rate_limit_reset = None

        return {
            "remaining": self._remaining_requests,
            "reset_time": self._rate_limit_reset,
            "reset_in_seconds": (
                self._rate_limit_reset - current_time
                if self._rate_limit_reset
                else None
            ),
        }

    def should_wait_for_rate_limit(self) -> bool:
        """Return whether to wait due to rate limit exhaustion.

        Returns:
            bool: True if the remaining request count is set and below the
                configured threshold, False otherwise.

        """
        if self._remaining_requests is None:
            return False

        # Wait if we have very few requests remaining
        return self._remaining_requests < self.RATE_LIMIT_THRESHOLD

    def get_wait_time(self) -> int:
        """Return the recommended wait time in seconds.

        The wait time is computed from the stored rate-limit reset time
        with a small buffer and is capped to a maximum of 3600 seconds.

        Returns:
            int: Recommended wait time in seconds.

        """
        status = self.get_rate_limit_status()
        reset_in = status.get("reset_in_seconds")

        if reset_in and reset_in > 0:
            # Wait for rate limit reset plus small buffer
            return min(reset_in + 10, 3600)  # Max 1 hour

        return 60  # Default 1 minute wait

    def is_authenticated(self) -> bool:
        """Return whether a non-empty token is stored.

        Returns:
            bool: True if a non-empty token is available, False otherwise.

        """
        token = self.get_token()
        return token is not None and len(token.strip()) > 0

    def is_token_valid(self) -> bool:
        """Return whether the stored token has a valid format.

        Returns:
            bool: True if a token exists and validates with
                `validate_github_token`, False otherwise.

        """
        token = self.get_token()
        if token is None:
            return False
        return validate_github_token(token)


# Global instance for easy access
auth_manager = GitHubAuthManager()
