#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Secure token management module.

This module handles secure storage and retrieval of API tokens using the system's
keyring when available, with a fallback to encrypted file storage.
"""

import base64
import getpass
import json
import logging
import os
import time
import uuid
import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

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
TOKEN_METADATA_FILE = CONFIG_DIR / ".token.meta"
# Default token expiration in days (90 days is a common security standard)
DEFAULT_TOKEN_EXPIRATION_DAYS = 90

# Try to detect available keyring backends
KEYRING_AVAILABLE = False
GNOME_KEYRING_AVAILABLE = False
KDE_WALLET_AVAILABLE = False

# Try to import keyring - support both virtual environment and system installs
keyring_module = None
try:
    # First try to import from normal paths
    import keyring

    keyring_module = keyring

    # Try to import backends - but make them optional
    HAVE_SECRETSERVICE = False
    HAVE_KWALLET = False
    try:
        from keyring.backends import SecretService

        HAVE_SECRETSERVICE = True
    except ImportError:
        logger.debug("SecretService backend not available")

    try:
        from keyring.backends import KWallet

        HAVE_KWALLET = True
    except ImportError:
        logger.debug("KWallet backend not available")

    # Log the detected keyring backend and path for debugging
    logger.info(f"Keyring module found at: {keyring.__file__}")
    try:
        logger.info(
            f"Available backends: {[b.__class__.__name__ for b in keyring.backend.get_all_keyring()]}"
        )
    except Exception as e:
        logger.warning(f"Could not list keyring backends: {e}")

    # Check if GNOME keyring (Seahorse) is available
    try:
        # Only check for GNOME keyring if SecretService is available
        if HAVE_SECRETSERVICE:
            # Improved GNOME keyring detection
            secretservice_backend = SecretService.Keyring()

            # Check for D-Bus connectivity first (more reliable than direct collection check)
            import dbus

            bus = dbus.SessionBus()
            # Check if the Secret Service is available on the bus
            if bus.name_has_owner("org.freedesktop.secrets"):
                GNOME_KEYRING_AVAILABLE = True
                logger.info("Seahorse/GNOME keyring detected")
    except ImportError:
        logger.debug("D-Bus Python module not available, falling back to direct check")
        try:
            # Only check if SecretService is available
            if HAVE_SECRETSERVICE:
                # Fallback detection without D-Bus module
                if hasattr(secretservice_backend, "get_preferred_collection"):
                    # Don't call the method, just check if it exists to avoid exceptions
                    GNOME_KEYRING_AVAILABLE = True
                    logger.info("Seahorse/GNOME keyring detected (fallback method)")
        except Exception as e:
            logger.debug(f"Seahorse/GNOME keyring not available: {e}")
    except Exception as e:
        logger.debug(f"Seahorse/GNOME keyring not available: {e}")

    # Check if KDE Wallet is available
    try:
        # Only check for KDE Wallet if available
        if HAVE_KWALLET:
            kwallet_backend = KWallet.Keyring()
            if kwallet_backend.priority > 0:  # KWallet has a valid priority when available
                KDE_WALLET_AVAILABLE = True
                logger.info("KDE Wallet detected")
    except Exception as e:
        logger.debug(f"KDE Wallet not available: {e}")

    # Set overall keyring availability
    KEYRING_AVAILABLE = GNOME_KEYRING_AVAILABLE or KDE_WALLET_AVAILABLE

    # If no supported keyring was found but keyring is imported, log more details
    if not KEYRING_AVAILABLE:
        try:
            # Check available backends
            backends = keyring.backend.get_all_keyring()
            if backends:
                backend_names = [b.__class__.__name__ for b in backends]
                logger.info(f"Available keyring backends (not supported): {backend_names}")

                # Allow using any available backend if none of our preferred ones are found
                if backends:
                    KEYRING_AVAILABLE = True
                    logger.info("Using available keyring backend even though it's not preferred")
            else:
                logger.warning("No keyring backends available")
        except Exception as e:
            logger.warning(f"Failed to enumerate keyring backends: {e}")

    # Configure keyring priority - prioritize GNOME keyring over KDE Wallet
    if GNOME_KEYRING_AVAILABLE and HAVE_SECRETSERVICE:
        try:
            # Different keyring versions use different methods
            if hasattr(keyring, "set_preferred_backend"):
                keyring.set_preferred_backend(SecretService.Keyring)
                logger.info(
                    "Using Seahorse/GNOME keyring as preferred backend (set_preferred_backend)"
                )
            elif hasattr(keyring, "set_keyring"):
                keyring.set_keyring(SecretService.Keyring())
                logger.info("Using Seahorse/GNOME keyring as preferred backend (set_keyring)")
            else:
                logger.warning(
                    "Could not set GNOME keyring as preferred - no supported method found"
                )
        except Exception as e:
            logger.warning(f"Failed to set GNOME keyring as preferred: {e}")
    elif KDE_WALLET_AVAILABLE and HAVE_KWALLET:
        try:
            # Different keyring versions use different methods
            if hasattr(keyring, "set_preferred_backend"):
                keyring.set_preferred_backend(KWallet.Keyring)
                logger.info("Using KDE Wallet as preferred backend (set_preferred_backend)")
            elif hasattr(keyring, "set_keyring"):
                keyring.set_keyring(KWallet.Keyring())
                logger.info("Using KDE Wallet as preferred backend (set_keyring)")
            else:
                logger.warning("Could not set KDE Wallet as preferred - no supported method found")
        except Exception as e:
            logger.warning(f"Failed to set KDE Wallet as preferred: {e}")

except ImportError as e:
    logger.warning(f"Keyring module not available in current Python path: {e}")

    # Try to import from system Python as fallback
    try:
        import subprocess
        import sys

        # Find system Python path
        python_path = subprocess.check_output(["which", "python3"]).decode().strip()
        logger.info(f"Attempting to use system Python at: {python_path}")

        # Get system Python version
        version_info = subprocess.check_output([python_path, "-V"]).decode().strip()
        logger.info(f"System Python version: {version_info}")

        # Try to import keyring from system Python
        result = subprocess.run(
            [python_path, "-c", "import keyring; print('KEYRING_FOUND')"],
            capture_output=True,
            text=True,
        )

        if "KEYRING_FOUND" in result.stdout:
            logger.info("Found keyring in system Python")
            KEYRING_AVAILABLE = True

            # Create a proxy class to use system Python's keyring via subprocess
            class SystemPythonKeyring:
                @staticmethod
                def set_password(service, username, password):
                    cmd = (
                        f'import keyring; keyring.set_password("{service}", "{username}", """'
                        + password
                        + '""")'
                    )
                    result = subprocess.run(
                        [python_path, "-c", cmd], capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        raise Exception(f"Failed to set password: {result.stderr}")
                    return True

                @staticmethod
                def get_password(service, username):
                    cmd = f'import keyring; print(keyring.get_password("{service}", "{username}"))'
                    result = subprocess.run(
                        [python_path, "-c", cmd], capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        raise Exception(f"Failed to get password: {result.stderr}")
                    return result.stdout.strip() or None

                @staticmethod
                def delete_password(service, username):
                    cmd = f'import keyring; keyring.delete_password("{service}", "{username}")'
                    result = subprocess.run(
                        [python_path, "-c", cmd], capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        raise Exception(f"Failed to delete password: {result.stderr}")
                    return True

            # Use our proxy class
            keyring_module = SystemPythonKeyring
            logger.info("Using system Python keyring via subprocess")

            # Check for GNOME keyring
            result = subprocess.run(
                [python_path, "-c", "import keyring.backends.SecretService; print('GNOME_FOUND')"],
                capture_output=True,
                text=True,
            )
            if "GNOME_FOUND" in result.stdout:
                GNOME_KEYRING_AVAILABLE = True
                logger.info("GNOME keyring available in system Python")

            # Check for KDE Wallet
            result = subprocess.run(
                [python_path, "-c", "import keyring.backends.KWallet; print('KDE_FOUND')"],
                capture_output=True,
                text=True,
            )
            if "KDE_FOUND" in result.stdout:
                KDE_WALLET_AVAILABLE = True
                logger.info("KDE Wallet available in system Python")

        else:
            logger.warning("Keyring not found in system Python either")
            KEYRING_AVAILABLE = False

    except Exception as e:
        logger.warning(f"Failed to use system Python keyring: {e}")
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
    def get_token(validate_expiration: bool = True) -> str:
        """
        Retrieve the GitHub token from secure storage.

        Tries multiple retrieval methods in order of security preference:
        1. Seahorse/GNOME keyring (if available)
        2. KDE Wallet (if available)
        3. Encrypted file (if available)

        Args:
            validate_expiration: Whether to check if the token has expired

        Returns:
            str: The GitHub token or empty string if not found or expired
        """
        token = ""
        metadata = {}

        # Try system keyring first
        if KEYRING_AVAILABLE:
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
                        logger.debug(f"Could not parse token metadata {e}")
                        metadata = {}

                    if GNOME_KEYRING_AVAILABLE:
                        logger.info("Retrieved GitHub token from Seahorse/GNOME keyring")
                    elif KDE_WALLET_AVAILABLE:
                        logger.info("Retrieved GitHub token from KDE Wallet")
                    else:
                        logger.info("Retrieved GitHub token from system keyring")
            except Exception as e:
                logger.warning(f"Could not retrieve from system keyring: {e}")

        # Try encrypted file as fallback
        if not token and CRYPTO_AVAILABLE and TOKEN_FILE.exists():
            try:
                key = SecureTokenManager._get_encryption_key()

                with open(TOKEN_FILE, "rb") as f:
                    encrypted_token = f.read()

                fernet = Fernet(key)
                token = fernet.decrypt(encrypted_token).decode("utf-8")
                logger.info("Retrieved GitHub token from encrypted file")

                # Try to get metadata
                if TOKEN_METADATA_FILE.exists():
                    try:
                        with open(TOKEN_METADATA_FILE, "r") as f:
                            metadata = json.load(f)
                    except Exception as e:
                        logger.debug(f"Could not retrieve token metadata from file: {e}")
            except Exception as e:
                logger.error(f"Failed to retrieve token from encrypted file: {e}")

        # If token was found but we need to validate expiration
        if token and validate_expiration and metadata:
            try:
                now = int(time.time())
                if "expires_at" in metadata:
                    # Handle both string and integer timestamp formats
                    expires_at = metadata["expires_at"]
                    if isinstance(expires_at, str):
                        try:
                            # Try parsing as ISO format date first
                            expires_at = int(datetime.datetime.fromisoformat(expires_at).timestamp())
                        except ValueError:
                            # Try parsing as a float/int string directly
                            expires_at = int(float(expires_at))
                        
                    if expires_at < now:
                        logger.warning("Token has expired and is no longer valid")
                        # Update usage stats but return empty token to indicate expiration
                        SecureTokenManager._update_token_usage_stats(metadata)
                        return ""
                # Update last used time
                SecureTokenManager._update_token_usage_stats(metadata)
            except Exception as e:
                logger.warning(f"Error validating token expiration: {e}")
        
        # If no token was found
        if not token:
            logger.warning("No GitHub token found in secure storage")

        return token

    @staticmethod
    def _update_token_usage_stats(metadata: Dict[str, Any]) -> None:
        """
        Update token usage statistics in metadata.

        Args:
            metadata: Token metadata dictionary
        """
        if not metadata:
            return

        # Update last used time
        metadata["last_used_at"] = int(time.time())

        # Save updated metadata
        if KEYRING_AVAILABLE:
            try:
                keyring_module.set_password(f"{SERVICE_NAME}_metadata", USERNAME, json.dumps(metadata))
            except Exception as e:
                logger.debug(f"Could not update token metadata in keyring: {e}")
        elif CRYPTO_AVAILABLE and TOKEN_METADATA_FILE.exists():
            try:
                temp_metadata_file = TOKEN_METADATA_FILE.with_suffix(".tmp")
                with open(temp_metadata_file, "w") as f:
                    json.dump(metadata, f)
                os.chmod(temp_metadata_file, 0o600)
                os.replace(temp_metadata_file, TOKEN_METADATA_FILE)
            except Exception as e:
                logger.debug(f"Could not update token metadata in file: {e}")

    @staticmethod
    def get_token_metadata() -> Dict[str, Any]:
        """
        Get metadata about the stored token.

        Returns:
            Dict: Token metadata including creation time and expiration
        """
        metadata = {}

        # Try system keyring first
        if KEYRING_AVAILABLE:
            try:
                metadata_str = keyring_module.get_password(f"{SERVICE_NAME}_metadata", USERNAME)
                if metadata_str:
                    metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                logger.debug(f"Could not decode token metadata from keyring")
                metadata = {}

        # Try encrypted file as fallback
        if not metadata and CRYPTO_AVAILABLE and TOKEN_METADATA_FILE.exists():
            try:
                with open(TOKEN_METADATA_FILE, "r") as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.debug(f"Could not retrieve token metadata from file: {e}")

        return metadata

    @staticmethod
    def is_token_expired() -> bool:
        """
        Check if the current token has expired.
    
        Returns:
            bool: True if token has expired or doesn't exist, False if valid
        """
        metadata = SecureTokenManager.get_token_metadata()
        if not metadata or "expires_at" not in metadata:
            # If we can't determine expiration, assume expired
            return True
    
        try:
            now = int(time.time())
            # Handle both string and integer timestamp formats
            expires_at = metadata["expires_at"]
            if isinstance(expires_at, str):
                try:
                    # Try parsing as ISO format date first
                    expires_at = int(datetime.datetime.fromisoformat(expires_at).timestamp())
                except ValueError:
                    # Try parsing as a float/int string directly
                    expires_at = int(float(expires_at))
            
            return expires_at < now
        except Exception as e:
            logger.warning(f"Error checking token expiration: {e}")
            return True  # Assume expired if there's an error

    @staticmethod
    def get_token_expiration_info() -> Tuple[bool, Optional[str]]:
        """
        Get token expiration information.
    
        Returns:
            Tuple[bool, Optional[str]]: (is_expired, expiration_date_string)
        """
        metadata = SecureTokenManager.get_token_metadata()
        if not metadata or "expires_at" not in metadata:
            return True, None
    
        try:
            now = int(time.time())
            # Handle both string and integer timestamp formats
            expires_at = metadata["expires_at"]
            if isinstance(expires_at, str):
                try:
                    # Try parsing as ISO format date first
                    from datetime import datetime
                    expires_at_ts = int(datetime.fromisoformat(expires_at).timestamp())
                except ValueError:
                    # Try parsing as a float/int string directly
                    expires_at_ts = int(float(expires_at))
            else:
                expires_at_ts = expires_at
                
            is_expired = expires_at_ts < now
    
            # Convert expiration timestamp to human-readable date
            try:
                expiration_date = datetime.fromtimestamp(expires_at_ts)
                expiration_str = expiration_date.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                expiration_str = None
    
            return is_expired, expiration_str
        except Exception as e:
            logger.warning(f"Error getting token expiration info: {e}")
            return True, None  # Assume expired if there's an error

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
                keyring_module.delete_password(SERVICE_NAME, USERNAME)
                # Also try to remove metadata
                try:
                    keyring_module.delete_password(f"{SERVICE_NAME}_metadata", USERNAME)
                except Exception:
                    pass

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

        # Remove metadata file if exists
        if TOKEN_METADATA_FILE.exists():
            try:
                os.remove(TOKEN_METADATA_FILE)
                logger.info("Removed token metadata file")
            except Exception as e:
                logger.error(f"Failed to remove token metadata file: {e}")

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
                token = keyring_module.get_password(SERVICE_NAME, USERNAME)
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
    def prompt_for_token() -> str:
        """
        Securely prompt the user for a GitHub token.

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

    @staticmethod
    def configure_keyring() -> bool:
        """
        Configure the Seahorse/GNOME keyring for secure token storage.

        This method provides a direct way to configure the GNOME keyring,
        bypassing the python-keyring library for more control.

        Returns:
            bool: True if configuration succeeded, False otherwise
        """
        try:
            print("\nAttempting to configure Seahorse/GNOME keyring...")

            # Check if seahorse is installed
            import subprocess
            import shutil

            # Check if Seahorse is installed
            if shutil.which("seahorse"):
                print("✅ Seahorse is installed")
            else:
                print("❌ Seahorse not found - attempting to configure manually")

            # Check if libsecret is available via Python direct bindings (more modern approach)
            try:
                import gi

                gi.require_version("Secret", "1.0")
                from gi.repository import Secret

                print("✅ Python GObject introspection for libsecret found")
                print("Using direct libsecret bindings (modern approach)")

                # Create a schema for our application
                schema = Secret.Schema.new(
                    "org.myunicorn.auth",
                    Secret.SchemaFlags.NONE,
                    {"service": Secret.SchemaAttributeType.STRING},
                )

                # Test if we can access the secret service
                success = Secret.Service.get_sync(Secret.ServiceFlags.LOAD_COLLECTIONS, None)
                if success:
                    print("✅ Successfully connected to Secret Service")

                    # Store a test secret to ensure everything works
                    test_stored = Secret.password_store_sync(
                        schema,  # The schema
                        {"service": "my-unicorn-test"},  # Attributes
                        Secret.COLLECTION_DEFAULT,  # Which keyring
                        "Test secret",  # Label for the secret
                        "test-secret-value",  # The secret itself
                        None,  # No cancellable
                    )

                    if test_stored:
                        print("✅ Successfully stored test secret")

                        # Retrieve it to make sure it works
                        retrieved = Secret.password_lookup_sync(
                            schema, {"service": "my-unicorn-test"}, None
                        )

                        if retrieved == "test-secret-value":
                            print("✅ Successfully retrieved test secret")

                            # Clean up the test secret
                            Secret.password_clear_sync(schema, {"service": "my-unicorn-test"}, None)
                            print("✅ Secret service configured and ready to use")
                            return True
                        else:
                            print("❌ Failed to retrieve test secret")
                    else:
                        print("❌ Failed to store test secret")
                else:
                    print("❌ Failed to connect to Secret Service")

            except (ImportError, ValueError) as e:
                print(f"❌ Python GObject introspection for libsecret not available: {e}")
                print("Falling back to D-Bus direct access (alternate approach)")

                # Fall back to direct D-Bus access
                try:
                    import dbus

                    # Connect to the Secret Service
                    bus = dbus.SessionBus()
                    service = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")

                    # Check if the service is accessible
                    service_interface = dbus.Interface(service, "org.freedesktop.Secret.Service")
                    collections = service_interface.GetCollections()

                    if collections:
                        print("✅ Successfully accessed Secret Service via D-Bus")
                        print("✅ Found keyring collections")
                        return True
                    else:
                        print("❌ Secret Service accessible but no collections found")
                except Exception as e:
                    print(f"❌ Direct D-Bus access failed: {e}")

            # If we get here, we didn't succeed with direct libsecret or D-Bus
            print("\nAttempting to launch Seahorse for manual configuration...")

            # Offer to launch seahorse if available
            if shutil.which("seahorse"):
                launch = input(
                    "Would you like to launch Seahorse to configure it manually? (y/n): "
                )
                if launch.lower() == "y":
                    result = subprocess.run(
                        ["seahorse"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    if result.returncode == 0:
                        print("\nSeahorse launched successfully. Please configure your keyring.")
                        print("1. In Seahorse, go to File > New > Password Keyring if none exists")
                        print("2. Name it 'login' for best compatibility")
                        print("3. Create and remember your keyring password")
                        print("4. Close Seahorse when done")

                        finished = input("\nPress Enter when you've completed the setup...")
                        return True
                    else:
                        print("❌ Failed to launch Seahorse")

            # Provide instructions for package installation
            print("\nTo install the required packages, run one of these commands:")
            print("For Ubuntu/Debian:")
            print("  sudo apt install seahorse libsecret-1-0 python3-secretstorage")
            print("For Fedora:")
            print("  sudo dnf install seahorse libsecret python3-gobject")
            print("For Arch Linux:")
            print("  sudo pacman -S seahorse libsecret python-gobject")

            return False

        except Exception as e:
            logger.error(f"Keyring configuration failed: {e}")
            print(f"❌ Keyring configuration failed: {e}")
            return False

    @staticmethod
    def audit_log_token_usage(action: str, source_ip: Optional[str] = None) -> None:
        """
        Log token usage for auditing purposes.

        Args:
            action: The action being performed with the token
            source_ip: Optional source IP for the request
        """
        try:
            metadata = SecureTokenManager.get_token_metadata()
            token_id = metadata.get("token_id", "unknown")

            audit_entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "action": action,
                "token_id": token_id,
                "source_ip": source_ip or "local",
            }

            # Write to audit log file
            audit_log_path = CONFIG_DIR / "token_audit.log"

            with open(audit_log_path, "a") as f:
                f.write(json.dumps(audit_entry) + "\n")

            # Set proper permissions
            try:
                os.chmod(audit_log_path, 0o600)
            except:
                pass

        except Exception as e:
            logger.debug(f"Failed to log token usage to audit log: {e}")

    @staticmethod
    def get_audit_logs() -> List[Dict[str, Any]]:
        """
        Get token usage audit logs.

        Returns:
            List[Dict[str, Any]]: List of audit log entries in reverse chronological order (newest first)
        """
        audit_logs = []
        audit_log_path = CONFIG_DIR / "token_audit.log"

        if not audit_log_path.exists():
            return audit_logs

        try:
            with open(audit_log_path, "r") as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        # Convert timestamp string to isoformat if it's not already
                        if "timestamp" in log_entry and not isinstance(log_entry["timestamp"], str):
                            log_entry["timestamp"] = datetime.datetime.fromtimestamp(
                                log_entry["timestamp"]
                            ).isoformat()
                        audit_logs.append(log_entry)
                    except json.JSONDecodeError:
                        logger.debug(f"Skipping invalid audit log entry: {line}")
                        continue

            # Sort logs by timestamp (newest first)
            audit_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {e}")

        return audit_logs

    @staticmethod
    def _create_token_metadata(token: str, expires_in_days: int, storage_info: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create basic token metadata.
        
        Args:
            token: The GitHub token to store
            expires_in_days: Number of days until token expiration
            storage_info: Optional initial storage information
            
        Returns:
            Dict[str, Any]: Token metadata
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
            "storage_method": "Auto-detect",
            "storage_location": "Not yet determined",
            "storage_status": "Pending",
        }
        
        # Update with provided storage info if any
        if storage_info:
            metadata.update(storage_info)
            
        return metadata
    
    @staticmethod
    def _save_to_keyring(token: str, metadata: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Save token to system keyring.
        
        Args:
            token: The GitHub token to store
            metadata: Token metadata
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, updated_metadata)
        """
        if not KEYRING_AVAILABLE:
            return False, metadata
            
        try:
            # Store token
            keyring_module.set_password(SERVICE_NAME, USERNAME, token)
    
            # Update metadata with storage information
            if GNOME_KEYRING_AVAILABLE:
                metadata["storage_method"] = "GNOME keyring"
                metadata["storage_location"] = "Seahorse/GNOME keyring"
                metadata["storage_status"] = "Active"
                metadata["gnome_keyring_name"] = "login"
            elif KDE_WALLET_AVAILABLE:
                metadata["storage_method"] = "KDE Wallet"
                metadata["storage_location"] = "KDE Wallet"
                metadata["storage_status"] = "Active"
            else:
                metadata["storage_method"] = "System keyring"
                metadata["storage_location"] = "Default system keyring"
                metadata["storage_status"] = "Active"
    
            # Store metadata separately
            metadata_json = json.dumps(metadata)
            keyring_module.set_password(f"{SERVICE_NAME}_metadata", USERNAME, metadata_json)
    
            if GNOME_KEYRING_AVAILABLE:
                logger.info("GitHub token saved to Seahorse/GNOME keyring")
            elif KDE_WALLET_AVAILABLE:
                logger.info("GitHub token saved to KDE Wallet")
            else:
                logger.info("GitHub token saved to system keyring")
    
            return True, metadata
        except Exception as e:
            logger.warning(f"Could not save to system keyring: {e}")
            return False, metadata
    
    @staticmethod
    def _save_to_encrypted_file(token: str, metadata: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Save token to encrypted file.
        
        Args:
            token: The GitHub token to store
            metadata: Token metadata
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, updated_metadata)
        """
        if not CRYPTO_AVAILABLE:
            return False, metadata
            
        try:
            # Ensure config directory exists with proper permissions
            os.makedirs(CONFIG_DIR, exist_ok=True)
    
            # Set secure directory permissions (only user can access)
            try:
                os.chmod(CONFIG_DIR, 0o700)
            except OSError as e:
                logger.warning(f"Could not set secure permissions on config directory: {e}")
    
            # Update metadata with storage information
            metadata["storage_method"] = "Encrypted file"
            metadata["storage_location"] = str(TOKEN_FILE)
            metadata["storage_status"] = "Active"
            metadata["encryption_type"] = "Fernet symmetric encryption"
    
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
    
            # Save metadata to separate file
            temp_metadata_file = TOKEN_METADATA_FILE.with_suffix(".tmp")
            with open(temp_metadata_file, "w") as f:
                json.dump(metadata, f)
    
            # Set secure file permissions before final move
            os.chmod(temp_metadata_file, 0o600)
    
            # Atomically replace the metadata file
            os.replace(temp_metadata_file, TOKEN_METADATA_FILE)
    
            logger.info("GitHub token saved to encrypted file with expiration metadata")
            return True, metadata
        except Exception as e:
            # Clean up temp files if they exist
            for temp_file in [TOKEN_FILE.with_suffix(".tmp"), TOKEN_METADATA_FILE.with_suffix(".tmp")]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            logger.error(f"Failed to save token to encrypted file: {e}")
            return False, metadata
    
    @staticmethod
    def save_token(token: str, expires_in_days: int = DEFAULT_TOKEN_EXPIRATION_DAYS, 
                storage_preference: str = "auto", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a GitHub token securely with expiration metadata.
    
        Tries multiple storage methods in order of security preference:
        1. Seahorse/GNOME keyring (if available)
        2. KDE Wallet (if available)
        3. Encrypted file (if cryptography module available)
    
        Args:
            token: The GitHub token to store
            expires_in_days: Number of days until token expiration (default: 90)
            storage_preference: Preferred storage method ("auto", "keyring", "gnome", "file")
            metadata: Optional additional metadata to include
    
        Returns:
            bool: True if successful, False otherwise
        """
        import re
        # Validate GitHub token format (ghp_, github_pat_, etc.)
        if not re.match(r'^(ghp_|github_pat_|gho_|ghu_|ghs_|ghr_)?[a-zA-Z0-9_\-]+$', token):
            logger.warning("Token appears to have an invalid format")
            return False
            
        # Validate token length (GitHub tokens are typically at least 40 chars)
        if len(token) < 40:
            logger.warning("Token appears to be too short to be valid")
            return False       
    
        # Create metadata
        metadata_dict = SecureTokenManager._create_token_metadata(
            token, expires_in_days, 
            {"storage_preference": storage_preference}
        )
        
        # Update with any provided custom metadata
        if metadata:
            metadata_dict.update(metadata)
        
        # Try system keyring first (most secure) if not explicitly requesting file storage
        if storage_preference in ("auto", "keyring", "keyring_only") and KEYRING_AVAILABLE:
            success, metadata_dict = SecureTokenManager._save_to_keyring(token, metadata_dict)
            if success:
                return True
                
        # If we've specified keyring_only but it failed, return failure
        if storage_preference == "keyring_only":
            logger.error("Failed to save to keyring and keyring_only mode was specified")
            return False              
                
        # Try encrypted file storage as fallback if not explicitly requesting keyring-only
        if storage_preference in ("auto", "file") and CRYPTO_AVAILABLE:
            # Ask for user approval before using encrypted file storage
            if ask_for_fallback and storage_preference == "auto":
                print("\nKeyring storage failed or not available.")
                print("The token can be stored in an encrypted file instead.")
                print("This is less secure than a system keyring but still provides protection.")
                
                response = input("Would you like to save your token in an encrypted file? (y/n): ")
                if response.lower() != 'y':
                    logger.info("User declined fallback to encrypted file storage")
                    return False
                    
            logger.info("Proceeding with encrypted file storage")
            success, metadata_dict = SecureTokenManager._save_to_encrypted_file(token, metadata_dict)
            if success:
                return True
    
        # If all else fails, indicate failure
        logger.error("No secure storage method available for token")
        return False
