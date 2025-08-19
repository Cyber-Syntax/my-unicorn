"""GitHub authentication and rate limiting management.

This module handles GitHub token storage, retrieval, and rate limiting
to ensure API requests are properly authenticated and don't exceed limits.
"""

import getpass
import time

import keyring
from keyring.backends import SecretService

from .logger import get_logger

logger = get_logger(__name__)

# Track keyring initialization to avoid redundant setup
_keyring_initialized: bool = False


def setup_keyring() -> None:
    """Set SecretService as the preferred keyring backend and log the result."""
    global _keyring_initialized

    if _keyring_initialized:
        return

    try:
        keyring.set_keyring(SecretService.Keyring())
        logger.debug("SecretService backend set as the preferred keyring backend")
        _keyring_initialized = True
    except Exception as e:
        logger.warning("Failed to set SecretService as the preferred keyring backend: %s", e)


# Initialize the keyring backend
setup_keyring()


class GitHubAuthManager:
    """Manages GitHub authentication tokens and rate limiting."""

    GITHUB_KEY_NAME: str = "my-unicorn-github-token"

    def __init__(self):
        """Initialize the auth manager with rate limit tracking."""
        self._rate_limit_reset: int | None = None
        self._remaining_requests: int | None = None
        self._last_check_time: float = 0

    @staticmethod
    def save_token() -> None:
        """Prompt user for GitHub token and save it securely."""
        token: str = getpass.getpass(prompt="Enter your GitHub token (input hidden): ")
        if not token.strip():
            raise ValueError("Token cannot be empty")

        keyring.set_password(GitHubAuthManager.GITHUB_KEY_NAME, "token", token)
        print("✅ Token securely saved to keyring.")

    @staticmethod
    def remove_token() -> None:
        """Remove GitHub token from keyring."""
        try:
            keyring.delete_password(GitHubAuthManager.GITHUB_KEY_NAME, "token")
            print("🗑️ Token removed from keyring.")
        except keyring.errors.PasswordDeleteError:
            print("❌ No token found to remove.")

    @staticmethod
    def get_token() -> str | None:
        """Retrieve GitHub token from keyring."""
        return keyring.get_password(GitHubAuthManager.GITHUB_KEY_NAME, "token")

    @staticmethod
    def apply_auth(headers: dict[str, str]) -> dict[str, str]:
        """Apply GitHub authentication to request headers."""
        token: str | None = GitHubAuthManager.get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def update_rate_limit_info(self, headers: dict[str, str]) -> None:
        """Update rate limit information from response headers."""
        try:
            # GitHub API uses capitalized header names
            self._remaining_requests = int(headers.get("X-RateLimit-Remaining", 0))
            self._rate_limit_reset = int(headers.get("X-RateLimit-Reset", 0))
            self._last_check_time = time.time()
        except (ValueError, TypeError):
            # Invalid headers, ignore
            pass

    def get_rate_limit_status(self) -> dict[str, int | None]:
        """Get current rate limit status."""
        current_time = int(time.time())

        # If reset time has passed, we can assume limits are reset
        if self._rate_limit_reset and current_time >= self._rate_limit_reset:
            self._remaining_requests = None
            self._rate_limit_reset = None

        return {
            "remaining": self._remaining_requests,
            "reset_time": self._rate_limit_reset,
            "reset_in_seconds": (
                self._rate_limit_reset - current_time if self._rate_limit_reset else None
            ),
        }

    # TODO: implement this method to install logics
    def should_wait_for_rate_limit(self) -> bool:
        """Check if we should wait due to rate limiting."""
        if self._remaining_requests is None:
            return False

        # Wait if we have very few requests remaining
        return self._remaining_requests < 10

    def get_wait_time(self) -> int:
        """Get recommended wait time in seconds."""
        status = self.get_rate_limit_status()
        reset_in = status.get("reset_in_seconds")

        if reset_in and reset_in > 0:
            # Wait for rate limit reset plus small buffer
            return min(reset_in + 10, 3600)  # Max 1 hour

        return 60  # Default 1 minute wait

    def is_authenticated(self) -> bool:
        """Check if we have a valid token stored."""
        token = self.get_token()
        return token is not None and len(token.strip()) > 0


# Global instance for easy access
auth_manager = GitHubAuthManager()
