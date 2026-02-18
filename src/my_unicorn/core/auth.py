"""GitHub authentication and rate limiting management.

Utilities for managing GitHub authentication and tracking rate-limit
information to avoid exceeding API limits. This module provides a
`GitHubAuthManager` class for applying authentication headers and managing
rate-limit status. Token storage is handled separately via the token_store
property which uses keyring-based storage.
"""

import time

from my_unicorn.core.token import validate_github_token
from my_unicorn.logger import get_logger

from .token import KeyringTokenStore

logger = get_logger(__name__)


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
