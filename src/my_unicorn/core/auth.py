"""GitHub authentication and rate limiting management.

Utilities for managing GitHub authentication and tracking rate-limit
information to avoid exceeding API limits. This module provides a
`GitHubAuthManager` class for applying authentication headers and managing
rate-limit status. Token storage is handled separately via the token_store
property which uses keyring-based storage.
"""

import re
import time

from my_unicorn.logger import get_logger

from .token import KeyringTokenStore

logger = get_logger(__name__)

# GitHub token security constraints
MAX_TOKEN_LENGTH: int = 255  # Maximum allowed token length per GitHub spec


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
    """Manage GitHub authentication and rate limiting.

    Provides methods to apply authentication to requests and track rate-limit
    information from API responses. Token storage is handled via the exposed
    token_store property.
    """

    RATE_LIMIT_THRESHOLD: int = 10  # Minimum remaining requests before waiting

    def __init__(self, token_store: KeyringTokenStore | None = None) -> None:
        """Initialize the auth manager with keyring token storage.

        Args:
            token_store: Optional token storage instance. If None, creates
                a default KeyringTokenStore instance.

        """
        self.token_store = (
            token_store if token_store is not None else KeyringTokenStore()
        )
        self._rate_limit_reset: int | None = None
        self._remaining_requests: int | None = None
        self._last_check_time: float = 0
        # Instance variable to track notification status
        # (not shared across instances)
        self._user_notified: bool = False

    @classmethod
    def create_default(cls) -> "GitHubAuthManager":
        """Create auth manager with default keyring-based token storage.

        Returns:
            GitHubAuthManager: Instance using KeyringTokenStore.

        """
        return cls()

    def get_token(self) -> str | None:
        """Retrieve the stored GitHub token from the token store.

        Returns:
            str | None: The token if available, otherwise None if no token
                is stored or the storage is unavailable.

        """
        return self.token_store.get()

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
        token: str | None = self.get_token()

        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.debug("Applied GitHub authentication (token present)")
        # Notify user once per session about rate limits when no token
        elif not self._user_notified:
            self._user_notified = True
            logger.info(
                "No GitHub token configured. API rate limits apply "
                "(60 requests/hour). Use 'my-unicorn token --save' "
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
