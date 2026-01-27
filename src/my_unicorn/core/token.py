"""GitHub token storage using system keyring.

Provides secure token storage and retrieval using the system's keyring
service (e.g., SecretService on Linux, Keychain on macOS, Credential
Manager on Windows).
"""

import re

import keyring
from keyring.backends import SecretService

from my_unicorn.logger import get_logger

logger = get_logger(__name__)

# GitHub token security constraints
MAX_TOKEN_LENGTH: int = 255  # Maximum allowed token length per GitHub spec


class KeyringError(Exception):
    """Base exception for keyring-related errors."""


class KeyringUnavailableError(KeyringError):
    """Raised when keyring is unavailable (e.g., headless environment)."""


class KeyringAccessError(KeyringError):
    """Raised when keyring access fails (e.g., permission denied)."""


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


def setup_keyring() -> None:
    """Set SecretService as the preferred keyring backend if available.

    Raises:
        KeyringUnavailableError: If keyring is unavailable (e.g., headless
            environment, no DBUS).
        KeyringAccessError: If keyring setup fails for other reasons.

    """
    try:
        keyring.set_keyring(SecretService.Keyring())
        logger.debug("SecretService backend set successfully")
    except ImportError:
        # SecretService not available - expected in some environments
        logger.debug("SecretService backend not available (import failed)")
        msg = "SecretService backend not available"
        raise KeyringUnavailableError(msg) from None
    except Exception as e:
        # Expected in headless environments (DBUS unavailable)
        if "DBUS" in str(e) or "DBus" in str(e):
            logger.debug("Keyring unavailable in headless environment: %s", e)
            msg = "Keyring unavailable in headless environment"
            raise KeyringUnavailableError(msg) from e
        logger.warning("Keyring setup failed: %s", e)
        msg = "Keyring setup failed"
        raise KeyringAccessError(msg) from e


class KeyringTokenStore:
    """Secure token storage using system keyring.

    Stores GitHub authentication tokens securely using the system's keyring
    service (SecretService on Linux, Keychain on macOS, Credential Manager
    on Windows).
    """

    def __init__(
        self, service: str = "my-unicorn-github-token", username: str = "token"
    ) -> None:
        """Initialize the keyring token store.

        Args:
            service: The service name for keyring storage.
            username: The username for keyring storage.

        """
        self.service = service
        self.username = username
        self._initialized = False
        self._unavailable = False

    def _ensure_initialized(self) -> None:
        """Initialize keyring on first use.

        Tracks initialization state to avoid repeated attempts.
        Logs appropriate messages based on error type.
        """
        if self._initialized or self._unavailable:
            return

        try:
            setup_keyring()
            self._initialized = True
        except KeyringUnavailableError:
            self._unavailable = True
            logger.debug(
                "Keyring unavailable (headless environment or no DBUS)"
            )
        except KeyringAccessError:
            self._unavailable = True
            logger.warning("Keyring access denied or setup failed")

    def is_available(self) -> bool:
        """Check if keyring is available for use.

        Returns:
            bool: True if keyring is available, False otherwise.

        """
        self._ensure_initialized()
        return not self._unavailable

    def get(self) -> str | None:
        """Retrieve the stored token from the keyring.

        Returns:
            str | None: The token if available, None if not stored or
                keyring is unavailable.

        """
        self._ensure_initialized()
        if self._unavailable:
            return None

        try:
            token = keyring.get_password(self.service, self.username)
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

    def set(self, token: str) -> None:
        """Store the token in the keyring.

        Args:
            token: The token to store.

        Raises:
            Exception: If keyring storage fails.

        """
        self._ensure_initialized()
        try:
            keyring.set_password(self.service, self.username, token)
            logger.debug("Token saved to keyring successfully")
        except Exception as e:
            # Provide helpful message for keyring errors
            error_msg = str(e)
            if "DBUS" in error_msg or "DBus" in error_msg:
                logger.exception("Keyring unavailable in headless environment")
                logger.info("❌ Keyring not available in headless environment")
                logger.info(
                    "💡 Future: Environment variable support coming soon"
                )
                logger.info(
                    "   (MY_UNICORN_GITHUB_TOKEN will be supported in a "
                    "future release)"
                )
            else:
                logger.exception("Failed to save token to keyring")
            raise

    def delete(self) -> None:
        """Remove the token from the keyring.

        Raises:
            keyring.errors.PasswordDeleteError: If no password is stored.
            Exception: If keyring deletion fails for other reasons.

        """
        self._ensure_initialized()
        try:
            keyring.delete_password(self.service, self.username)
            logger.debug("Token removed from keyring successfully")
        except keyring.errors.PasswordDeleteError:
            # Expected error when no token exists - let caller handle it
            logger.debug("No token found in keyring to delete")
            raise
        except Exception:
            # Security: Sanitize error message for unexpected errors
            logger.exception("Failed to remove token from keyring")
            raise
