#!/usr/bin/env python3
"""Secure token management module.

This module handles secure storage and retrieval of API tokens using the GNOME keyring.
"""

import contextlib
import getpass
import json
import logging
import time
import uuid
from typing import Any

import keyring

from my_unicorn.utils.datetime_utils import format_timestamp, parse_timestamp

# Configure module logger
logger = logging.getLogger(__name__)

# Constants for keyring and storage
SERVICE_NAME = "my-unicorn-github"
USERNAME = "github-api"
# Default token expiration in days (90 days is a common security standard)
DEFAULT_TOKEN_EXPIRATION_DAYS = 90

# Minimum GitHub token length for validation
MIN_GITHUB_TOKEN_LENGTH = 40

# Try to detect GNOME keyring availability
gnome_keyring_available = False

# Try to import keyring and GNOME keyring support
keyring_module = None
try:
    # First try to import from normal paths

    keyring_module = keyring

    # Try to import GNOME keyring backend
    try:
        from keyring.backends import SecretService

        logger.info("Keyring module found at: %s", keyring.__file__)

        # Check if GNOME keyring (Seahorse) is available
        try:
            # Check for GNOME keyring if SecretService is available
            secretservice_backend = SecretService.Keyring()

            # Check for D-Bus connectivity first (more reliable than direct collection check)
            import dbus

            bus = dbus.SessionBus()
            # Check if the Secret Service is available on the bus
            if bus.name_has_owner("org.freedesktop.secrets"):
                gnome_keyring_available = True
                logger.info("Seahorse/GNOME keyring detected")
        except ImportError:
            logger.debug("D-Bus Python module not available, falling back to direct check")
            try:
                # Fallback detection without D-Bus module
                secretservice_backend = SecretService.Keyring()
                if hasattr(secretservice_backend, "get_preferred_collection"):
                    # Don't call the method, just check if it exists to avoid exceptions
                    gnome_keyring_available = True
                    logger.info("Seahorse/GNOME keyring detected (fallback method)")
            except (ImportError, AttributeError) as e:
                logger.debug("Seahorse/GNOME keyring not available: %s", e)
        except (AttributeError, RuntimeError) as e:
            logger.debug("Seahorse/GNOME keyring not available: %s", e)

        # Configure keyring priority - use GNOME keyring as preferred backend
        if gnome_keyring_available:
            try:
                # Different keyring versions use different methods
                if hasattr(keyring, "set_preferred_backend"):
                    keyring.set_preferred_backend(SecretService.Keyring)
                    logger.info("Using Seahorse/GNOME keyring as preferred backend")
                elif hasattr(keyring, "set_keyring"):
                    keyring.set_keyring(SecretService.Keyring())
                    logger.info("Using Seahorse/GNOME keyring as preferred backend")
                else:
                    logger.warning(
                        "Could not set GNOME keyring as preferred - no supported method found"
                    )
            except (AttributeError, ImportError) as e:
                logger.warning("Failed to set GNOME keyring as preferred: %s", e)

    except ImportError:
        logger.debug("SecretService backend not available")

except ImportError as e:
    logger.warning("Keyring module not available in current Python path: %s", e)
    gnome_keyring_available = False


class SecureTokenManager:
    """Manages secure storage and retrieval of API tokens using GNOME keyring.

    This class provides methods to save and retrieve tokens securely using the GNOME
    keyring service (Seahorse). Only GNOME keyring is supported for maximum security
    and simplicity.

    Attributes:
        None - This class uses only static methods

    """

    @staticmethod
    def get_token(validate_expiration: bool = True) -> str:
        """Retrieve the GitHub token from GNOME keyring.

        Args:
            validate_expiration: Whether to check if the token has expired

        Returns:
            str: The GitHub token or empty string if not found or expired

        """
        token = ""
        metadata = {}

        # Try GNOME keyring
        if gnome_keyring_available and keyring_module:
            try:
                token = keyring_module.get_password(SERVICE_NAME, USERNAME)
                if token:
                    # Try to get metadata
                    try:
                        metadata_str = keyring_module.get_password(
                            f"{SERVICE_NAME}_metadata", USERNAME
                        )
                        if metadata_str:
                            metadata = json.loads(metadata_str)
                    except json.JSONDecodeError as e:
                        logger.debug("Could not parse token metadata: %s", e)
                        metadata = {}

                    logger.info("Retrieved GitHub token from Seahorse/GNOME keyring")
            except (KeyError, AttributeError, OSError) as e:
                logger.warning("Could not retrieve from GNOME keyring: %s", e)

        # If token was found but we need to validate expiration
        if token and validate_expiration and metadata:
            try:
                now = int(time.time())
                if "expires_at" in metadata:
                    # Use the utility function to parse timestamp
                    expires_dt = parse_timestamp(metadata["expires_at"])
                    if expires_dt:
                        expires_at = int(expires_dt.timestamp())
                        if expires_at < now:
                            logger.warning("Token has expired and is no longer valid")
                            # Update usage stats but return empty token to indicate expiration
                            SecureTokenManager._update_token_usage_stats(metadata)
                            return ""
                # Update last used time
                SecureTokenManager._update_token_usage_stats(metadata)
            except (ValueError, KeyError) as e:
                logger.warning("Error validating token expiration: %s", e)

        # If no token was found
        if not token:
            logger.warning("No GitHub token found in GNOME keyring")
            return ""

        return token

    @staticmethod
    def _update_token_usage_stats(metadata: dict[str, Any]) -> None:
        """Update token usage statistics in metadata.

        Args:
            metadata: Token metadata dictionary

        """
        if not metadata:
            return

        # Update last used time
        metadata["last_used_at"] = int(time.time())

        # Save updated metadata to GNOME keyring
        if gnome_keyring_available and keyring_module:
            try:
                keyring_module.set_password(
                    f"{SERVICE_NAME}_metadata", USERNAME, json.dumps(metadata)
                )
            except (KeyError, AttributeError) as e:
                logger.debug("Could not update token metadata in keyring: %s", e)

    @staticmethod
    def get_token_metadata() -> dict[str, Any]:
        """Get metadata about the stored token.

        Returns:
            dict: Token metadata including creation time and expiration

        """
        metadata = {}

        # Try GNOME keyring
        if gnome_keyring_available and keyring_module:
            try:
                metadata_str = keyring_module.get_password(
                    f"{SERVICE_NAME}_metadata", USERNAME
                )
                if metadata_str:
                    metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                logger.debug("Could not decode token metadata from keyring")
                metadata = {}

        return metadata

    @staticmethod
    def is_token_expired() -> bool:
        """Check if the current token has expired.

        Returns:
            bool: True if token has expired or doesn't exist, False if valid

        """
        metadata = SecureTokenManager.get_token_metadata()
        if not metadata or "expires_at" not in metadata:
            # If we can't determine expiration, assume expired
            return True

        try:
            now = int(time.time())
            # Use the utility function to parse timestamp
            expires_dt = parse_timestamp(metadata["expires_at"])
            if expires_dt:
                return expires_dt.timestamp() < now
            return True  # Assume expired if parsing fails
        except (ValueError, KeyError) as e:
            logger.warning("Error checking token expiration: %s", e)
            return True  # Assume expired if there's an error

    @staticmethod
    def get_token_expiration_info() -> tuple[bool, str | None]:
        """Get token expiration information.

        Returns:
            tuple[bool, Optional[str]]: (is_expired, expiration_date_string)

        """
        metadata = SecureTokenManager.get_token_metadata()
        if not metadata or "expires_at" not in metadata:
            return True, None

        try:
            now = int(time.time())
            # Use the utility function to parse timestamp
            expires_dt = parse_timestamp(metadata["expires_at"])
            if not expires_dt:
                return True, None

            is_expired = expires_dt.timestamp() < now

            # Format expiration date as string
            expiration_str = format_timestamp(expires_dt)

            return is_expired, expiration_str
        except (ValueError, KeyError) as e:
            logger.warning("Error getting token expiration info: %s", e)
            return True, None  # Assume expired if there's an error

    @staticmethod
    def remove_token() -> bool:
        """Remove the GitHub token from GNOME keyring.

        Returns:
            bool: True if removal was successful, False otherwise

        """
        success = False

        # Remove from GNOME keyring if available
        if gnome_keyring_available and keyring_module:
            try:
                keyring_module.delete_password(SERVICE_NAME, USERNAME)
                # Also try to remove metadata
                with contextlib.suppress(KeyError, AttributeError):
                    keyring_module.delete_password(f"{SERVICE_NAME}_metadata", USERNAME)

                logger.info("Removed GitHub token from Seahorse/GNOME keyring")
                success = True
            except (KeyError, AttributeError, OSError) as e:
                logger.warning("Could not remove from GNOME keyring: %s", e)

        return success

    @staticmethod
    def token_exists() -> bool:
        """Check if a token exists in GNOME keyring.

        Returns:
            bool: True if a token exists, False otherwise

        """
        # Check GNOME keyring
        if gnome_keyring_available and keyring_module:
            try:
                token = keyring_module.get_password(SERVICE_NAME, USERNAME)
                if token:
                    return True
            except (KeyError, AttributeError):
                pass

        return False

    @staticmethod
    def get_keyring_status() -> dict[str, bool]:
        """Get the status of available keyring backends.

        Returns:
            dict[str, bool]: Dictionary with status of keyring backends

        """
        return {
            "gnome_keyring_available": gnome_keyring_available,
        }

    @staticmethod
    def _create_token_metadata(token: str, expires_in_days: int) -> dict[str, Any]:
        """Create basic token metadata.

        Args:
            token: The GitHub token to store
            expires_in_days: Number of days until token expiration

        Returns:
            dict: Token metadata

        """
        if not token:
            logger.warning("Attempted to create metadata for an empty token")
            return {}

        # Generate token metadata
        token_id = str(uuid.uuid4())
        creation_time = int(time.time())
        expiration_time = creation_time + (expires_in_days * 86400)  # Convert days to seconds

        # Prepare metadata
        metadata = {
            "token_id": token_id,
            "created_at": creation_time,
            "expires_at": expiration_time,
            "last_used_at": creation_time,
            "scopes": "unknown",  # Will be updated when actually used with GitHub API
            "storage_method": "GNOME keyring",
            "storage_location": "Seahorse/GNOME keyring",
            "storage_status": "Active",
        }

        return metadata

    @staticmethod
    def save_token(
        token: str,
        expires_in_days: int = DEFAULT_TOKEN_EXPIRATION_DAYS,
    ) -> bool:
        """Save a GitHub token securely to GNOME keyring with expiration metadata.

        Args:
            token: The GitHub token to store
            expires_in_days: Number of days until token expiration (default: 90)

        Returns:
            bool: True if successful, False otherwise

        """
        import re

        # Validate GitHub token format (ghp_, github_pat_, etc.)
        if not re.match(r"^(ghp_|github_pat_|gho_|ghu_|ghs_|ghr_)?[a-zA-Z0-9_\-]+$", token):
            logger.warning("Token appears to have an invalid format")
            return False

        # Validate token length (GitHub tokens are typically at least 40 chars)
        if len(token) < MIN_GITHUB_TOKEN_LENGTH:
            logger.warning("Token appears to be too short to be valid")
            return False

        # Create metadata
        metadata = SecureTokenManager._create_token_metadata(token, expires_in_days)

        # Save to GNOME keyring
        if gnome_keyring_available and keyring_module:
            try:
                # Store token
                keyring_module.set_password(SERVICE_NAME, USERNAME, token)

                # Update metadata with storage information
                metadata["storage_method"] = "GNOME keyring"
                metadata["storage_location"] = "Seahorse/GNOME keyring"
                metadata["storage_status"] = "Active"
                metadata["gnome_keyring_name"] = "login"

                # Store metadata separately
                metadata_json = json.dumps(metadata)
                keyring_module.set_password(
                    f"{SERVICE_NAME}_metadata", USERNAME, metadata_json
                )

                logger.info("GitHub token saved to Seahorse/GNOME keyring")
                return True
            except (KeyError, AttributeError, OSError) as e:
                logger.warning("Could not save to GNOME keyring: %s", e)
                return False

        # If GNOME keyring is not available, fail
        logger.error("GNOME keyring is not available for secure token storage")
        return False

    @staticmethod
    def prompt_for_token() -> str:
        """Securely prompt the user for a GitHub token.

        Returns:
            str: The entered token or empty string if cancelled

        """
        print("\nEnter your GitHub token (or press Enter to cancel):")
        print("Create one at: https://github.com/settings/tokens")
        print("Tip: For rate limits only, you can create a token with NO permissions/scopes")

        try:
            token = getpass.getpass("Token: ")
            return token.strip()
        except (KeyboardInterrupt, EOFError):
            print("\nToken entry cancelled.")
            return ""
