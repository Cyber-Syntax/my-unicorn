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
        raise KeyringUnavailableError(
            "SecretService backend not available"
        ) from None
    except Exception as e:
        # Expected in headless environments (DBUS unavailable)
        if "DBUS" in str(e) or "DBus" in str(e):
            logger.debug("Keyring unavailable in headless environment: %s", e)
            raise KeyringUnavailableError(
                "Keyring unavailable in headless environment"
            ) from e
        logger.warning("Keyring setup failed: %s", e)
        raise KeyringAccessError("Keyring setup failed") from e


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


class GitHubAuthManager:
    """Manage GitHub authentication tokens and rate limiting.

    Provides helper methods to store and retrieve tokens, update rate-limit
    information from API responses, and apply authentication to outgoing
    requests.
    """

    GITHUB_KEY_NAME: str = "my-unicorn-github-token"
    RATE_LIMIT_THRESHOLD: int = 10  # Minimum remaining requests before waiting
    _user_notified: bool = False  # Track if user notified about rate limits

    def __init__(self):
        """Initialize the auth manager with rate limit tracking."""
        self._rate_limit_reset: int | None = None
        self._remaining_requests: int | None = None
        self._last_check_time: float = 0

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
        try:
            token: str = getpass.getpass(
                prompt="Enter your GitHub token (input hidden): "
            )
            if token is None:
                logger.error("No input received for GitHub token.")
                raise ValueError("Token cannot be empty")

            # Normalize input by stripping surrounding whitespace so accidental
            # spaces don't cause validation/confirmation mismatches. GitHub
            # tokens do not include leading/trailing whitespace in normal use.
            token = token.strip()
            if not token:
                logger.error("Attempted to save an empty GitHub token.")
                raise ValueError("Token cannot be empty")

            # Confirm token input
            confirm_token: str = getpass.getpass(
                prompt="Confirm your GitHub token: "
            )
            if confirm_token is None:
                logger.error(
                    "No input received for GitHub token confirmation."
                )
                raise ValueError("Token confirmation does not match")

            confirm_token = confirm_token.strip()
            if token != confirm_token:
                logger.error("GitHub token confirmation does not match.")
                raise ValueError("Token confirmation does not match")

            # Validate token format before saving
            if not validate_github_token(token):
                logger.error("Invalid GitHub token format provided.")
                raise ValueError(
                    "Invalid GitHub token format. "
                    "Must be a valid GitHub token."
                )

            keyring.set_password(
                GitHubAuthManager.GITHUB_KEY_NAME, "token", token
            )
            logger.info("GitHub token saved successfully.")
        except (EOFError, KeyboardInterrupt) as e:
            logger.error("GitHub token input aborted: %s", e)
            raise ValueError("Token input aborted by user") from e
        except Exception as e:
            # Provide helpful message for keyring errors
            error_msg = str(e)
            if "DBUS" in error_msg or "DBus" in error_msg:
                logger.exception(
                    "Keyring unavailable (headless environment): %s", e
                )
                logger.info("❌ Keyring not available in headless environment")
                logger.info(
                    "💡 Future: Environment variable support coming soon"
                )
                logger.info(
                    "   (MY_UNICORN_GITHUB_TOKEN will be supported in a "
                    "future release)"
                )
            else:
                logger.exception("Failed to save GitHub token to keyring")
            raise

    @staticmethod
    def remove_token() -> None:
        """Remove the stored GitHub token from the system keyring.

        Raises:
            Exception: If removal from the keyring fails for any reason.

        """
        try:
            keyring.delete_password(GitHubAuthManager.GITHUB_KEY_NAME, "token")
        except Exception as e:
            logger.error(f"Error removing GitHub token from keyring: {e}")
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
            if token:
                logger.debug(
                    "GitHub token retrieved from keyring (value hidden)"
                )
                return token
            logger.debug("No token stored in keyring")
            return None
        except Exception as e:
            # Keyring unavailable is expected in headless environments
            if "DBUS" in str(e) or "DBus" in str(e):
                logger.debug(
                    "Keyring unavailable (headless environment): %s", e
                )
            else:
                logger.debug("Keyring access failed: %s", e)
            return None

    @staticmethod
    def apply_auth(headers: dict[str, str]) -> dict[str, str]:
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
        elif not GitHubAuthManager._user_notified:
            GitHubAuthManager._user_notified = True
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
        except (ValueError, TypeError) as e:
            logger.warning("Invalid rate limit headers received: %s", e)
        except Exception as e:
            logger.error(f"Unexpected error updating rate limit info: {e}")

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
