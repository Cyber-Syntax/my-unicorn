#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Secure token management module.

This module handles secure storage and retrieval of API tokens using the system's
keyring when available, with a fallback to encrypted file storage.
"""

import base64
import getpass
import logging
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Configure module logger
logger = logging.getLogger(__name__)

# Constants for keyring and storage
SERVICE_NAME = "my-unicorn-github"
USERNAME = "github-api"
TOKEN_KEY = "github_token"
CONFIG_DIR = Path(os.path.expanduser("~/.config/myunicorn"))
SALT_FILE = CONFIG_DIR / ".token.salt"
KEY_FILE = CONFIG_DIR / ".token.key"
TOKEN_FILE = CONFIG_DIR / ".token.enc"

# Try to detect available keyring backends
KEYRING_AVAILABLE = False
GNOME_KEYRING_AVAILABLE = False
KDE_WALLET_AVAILABLE = False

try:
    import keyring
    from keyring.backends import SecretService, KWallet

    # Check if GNOME keyring (Seahorse) is available
    try:
        secretservice_backend = SecretService.Keyring()
        if secretservice_backend.get_preferred_collection():
            GNOME_KEYRING_AVAILABLE = True
            logger.info("Seahorse/GNOME keyring detected")
    except Exception as e:
        logger.debug(f"Seahorse/GNOME keyring not available: {e}")

    # Check if KDE Wallet is available
    try:
        kwallet_backend = KWallet.Keyring()
        if kwallet_backend.priority > 0:  # KWallet has a valid priority when available
            KDE_WALLET_AVAILABLE = True
            logger.info("KDE Wallet detected")
    except Exception as e:
        logger.debug(f"KDE Wallet not available: {e}")

    # Set overall keyring availability
    KEYRING_AVAILABLE = GNOME_KEYRING_AVAILABLE or KDE_WALLET_AVAILABLE

    # Configure keyring priority - prioritize GNOME keyring over KDE Wallet
    if GNOME_KEYRING_AVAILABLE:
        keyring.set_preferred_backend(SecretService.Keyring)
        logger.info("Using Seahorse/GNOME keyring as preferred backend")
    elif KDE_WALLET_AVAILABLE:
        keyring.set_preferred_backend(KWallet.Keyring)
        logger.info("Using KDE Wallet as preferred backend")

except ImportError:
    logger.warning("Keyring module not available - secure credential storage not supported")
    KEYRING_AVAILABLE = False

# Try to import cryptography for file-based fallback encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
    logger.info("Cryptography module available for file-based token encryption")
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("Cryptography module not available - encrypted file storage not supported")


class SecureTokenManager:
    """
    Manages secure storage and retrieval of API tokens.

    This class provides methods to save and retrieve tokens securely using the system's
    keyring when available, with fallbacks to encrypted file storage or configuration file.

    Attributes:
        None - This class uses only static methods
    """

    @staticmethod
    def save_token(token: str) -> bool:
        """
        Save a GitHub token securely.

        Tries multiple storage methods in order of security preference:
        1. Seahorse/GNOME keyring (if available)
        2. KDE Wallet (if available)
        3. Encrypted file (if cryptography module available)

        Args:
            token: The GitHub token to store

        Returns:
            bool: True if successful, False otherwise
        """
        if not token:
            logger.warning("Attempted to save an empty token")
            return False

        # Try system keyring first (most secure)
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(SERVICE_NAME, USERNAME, token)

                if GNOME_KEYRING_AVAILABLE:
                    logger.info("GitHub token saved to Seahorse/GNOME keyring")
                elif KDE_WALLET_AVAILABLE:
                    logger.info("GitHub token saved to KDE Wallet")
                else:
                    logger.info("GitHub token saved to system keyring")

                return True
            except Exception as e:
                logger.warning(f"Could not save to system keyring: {e}")

        # Try encrypted file storage as fallback
        if CRYPTO_AVAILABLE:
            try:
                # Ensure config directory exists with proper permissions
                os.makedirs(CONFIG_DIR, exist_ok=True)

                # Set secure directory permissions (only user can access)
                try:
                    os.chmod(CONFIG_DIR, 0o700)
                except OSError as e:
                    logger.warning(f"Could not set secure permissions on config directory: {e}")

                # Generate or retrieve encryption key
                key = SecureTokenManager._get_encryption_key()

                # Encrypt and save token
                fernet = Fernet(key)
                encrypted_token = fernet.encrypt(token.encode("utf-8"))

                # Use atomic write pattern with a temporary file
                temp_token_file = TOKEN_FILE.with_suffix(".tmp")
                with open(temp_token_file, "wb") as f:
                    f.write(encrypted_token)

                # Set secure file permissions before final move
                os.chmod(temp_token_file, 0o600)

                # Atomically replace the token file
                os.replace(temp_token_file, TOKEN_FILE)

                logger.info("GitHub token saved to encrypted file")
                return True
            except Exception as e:
                # Clean up temp file if it exists
                temp_token_file = TOKEN_FILE.with_suffix(".tmp")
                if os.path.exists(temp_token_file):
                    try:
                        os.remove(temp_token_file)
                    except:
                        pass
                logger.error(f"Failed to save token to encrypted file: {e}")

        # If all else fails, indicate failure
        logger.error("No secure storage method available for token")
        return False

    @staticmethod
    def get_token() -> str:
        """
        Retrieve the GitHub token from secure storage.

        Tries multiple retrieval methods in order of security preference:
        1. Seahorse/GNOME keyring (if available)
        2. KDE Wallet (if available)
        3. Encrypted file (if available)

        Returns:
            str: The GitHub token or empty string if not found
        """
        # Try system keyring first
        if KEYRING_AVAILABLE:
            try:
                token = keyring.get_password(SERVICE_NAME, USERNAME)
                if token:
                    if GNOME_KEYRING_AVAILABLE:
                        logger.info("Retrieved GitHub token from Seahorse/GNOME keyring")
                    elif KDE_WALLET_AVAILABLE:
                        logger.info("Retrieved GitHub token from KDE Wallet")
                    else:
                        logger.info("Retrieved GitHub token from system keyring")
                    return token
            except Exception as e:
                logger.warning(f"Could not retrieve from system keyring: {e}")

        # Try encrypted file as fallback
        if CRYPTO_AVAILABLE and TOKEN_FILE.exists():
            try:
                key = SecureTokenManager._get_encryption_key()

                with open(TOKEN_FILE, "rb") as f:
                    encrypted_token = f.read()

                fernet = Fernet(key)
                token = fernet.decrypt(encrypted_token).decode("utf-8")
                logger.info("Retrieved GitHub token from encrypted file")
                return token
            except Exception as e:
                logger.error(f"Failed to retrieve token from encrypted file: {e}")

        # If all else fails
        logger.warning("No GitHub token found in secure storage")
        return ""

    @staticmethod
    def remove_token() -> bool:
        """
        Remove the GitHub token from all storage locations.

        Returns:
            bool: True if removal was successful, False otherwise
        """
        success = False

        # Remove from keyring if available
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(SERVICE_NAME, USERNAME)

                if GNOME_KEYRING_AVAILABLE:
                    logger.info("Removed GitHub token from Seahorse/GNOME keyring")
                elif KDE_WALLET_AVAILABLE:
                    logger.info("Removed GitHub token from KDE Wallet")
                else:
                    logger.info("Removed GitHub token from system keyring")

                success = True
            except Exception as e:
                logger.warning(f"Could not remove from system keyring: {e}")

        # Remove token file if exists
        if TOKEN_FILE.exists():
            try:
                os.remove(TOKEN_FILE)
                logger.info("Removed encrypted token file")
                success = True
            except Exception as e:
                logger.error(f"Failed to remove token file: {e}")

        return success

    @staticmethod
    def token_exists() -> bool:
        """
        Check if a token exists in any storage location.

        Returns:
            bool: True if a token exists, False otherwise
        """
        # Check keyring
        if KEYRING_AVAILABLE:
            try:
                token = keyring.get_password(SERVICE_NAME, USERNAME)
                if token:
                    return True
            except Exception:
                pass

        # Check file storage
        if TOKEN_FILE.exists():
            return True

        return False

    @staticmethod
    def _get_encryption_key() -> bytes:
        """
        Get or create an encryption key for token storage.

        This method either retrieves an existing key or generates a new one
        based on a machine-specific identifier and a persistent salt value.

        Returns:
            bytes: An encryption key for Fernet symmetric encryption
        """
        # Create a machine-specific identifier to minimize asking for password
        machine_id = SecureTokenManager._get_machine_id()

        # Get or create a persistent salt
        salt = SecureTokenManager._get_or_create_salt()

        # Derive a key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        # Use machine ID as the "password" for key derivation
        key = base64.urlsafe_b64encode(kdf.derive(machine_id))

        # Save the key to avoid re-deriving it
        with open(KEY_FILE, "wb") as f:
            f.write(key)

        return key

    @staticmethod
    def _get_or_create_salt() -> bytes:
        """
        Get existing salt or create a new one.

        Returns:
            bytes: Salt value for key derivation
        """
        if SALT_FILE.exists():
            try:
                with open(SALT_FILE, "rb") as f:
                    return f.read()
            except (IOError, OSError) as e:
                logging.error(f"Failed to read salt file: {e}")
                # Generate a new salt if reading fails
                logging.info("Generating new salt due to read error")

        # Create a new salt with high entropy
        salt = os.urandom(32)  # Increased from 16 to 32 bytes for better security

        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)

            # Use atomic write pattern with a temporary file
            temp_salt_file = SALT_FILE.with_suffix(".tmp")
            with open(temp_salt_file, "wb") as f:
                f.write(salt)

            # Atomic rename for safer file operations
            os.replace(temp_salt_file, SALT_FILE)

            # Set restrictive permissions (only user can read/write)
            os.chmod(SALT_FILE, 0o600)

            logging.info("Created new salt file with secure permissions")

        except (IOError, OSError) as e:
            logging.error(f"Failed to create salt file: {e}")
            # Still return a valid salt even if file creation fails

        return salt

    @staticmethod
    def _get_machine_id() -> bytes:
        """
        Get a unique machine identifier or create one.

        This tries to use system-specific identifiers when available,
        falling back to a generated ID if needed.

        Returns:
            bytes: A reasonably stable machine-specific identifier
        """
        # Try to get a machine-specific ID from various sources
        machine_id = None

        # Try reading machine-id from standard Linux location
        if os.path.exists("/etc/machine-id"):
            try:
                with open("/etc/machine-id", "r") as f:
                    machine_id = f.read().strip()
            except Exception:
                pass

        # Fallback to hostname + user
        if not machine_id:
            import socket
            import getpass

            machine_id = f"{socket.gethostname()}-{getpass.getuser()}"

        return machine_id.encode("utf-8")

    @staticmethod
    def prompt_for_token(hide_input: bool = True) -> str:
        """
        Securely prompt the user for a GitHub token.

        Args:
            hide_input: Whether to hide user input during entry

        Returns:
            str: The entered token or empty string if cancelled
        """
        print("\nEnter your GitHub token (or press Enter to cancel):")
        print("Create one at: https://github.com/settings/tokens")
        print("Tip: For rate limits only, you can create a token with NO permissions/scopes")

        try:
            if hide_input:
                token = getpass.getpass("Token: ")
            else:
                token = input("Token: ")
            return token.strip()
        except (KeyboardInterrupt, EOFError):
            print("\nToken entry cancelled.")
            return ""

    @staticmethod
    def get_keyring_status() -> Dict[str, bool]:
        """
        Get the status of available keyring backends.

        Returns:
            Dict[str, bool]: Dictionary with status of keyring backends
        """
        return {
            "any_keyring_available": KEYRING_AVAILABLE,
            "gnome_keyring_available": GNOME_KEYRING_AVAILABLE,
            "kde_wallet_available": KDE_WALLET_AVAILABLE,
            "crypto_available": CRYPTO_AVAILABLE,
        }
