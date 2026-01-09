"""GitHub token storage using system keyring.

Provides secure token storage and retrieval using the system's keyring
service (e.g., SecretService on Linux, Keychain on macOS, Credential
Manager on Windows).
"""

import keyring
from keyring.backends import SecretService

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


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
