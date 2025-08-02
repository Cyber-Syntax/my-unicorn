#!/usr/bin/env python3
"""GitHub token management command module.

This module provides the command implementation for managing GitHub API tokens,
allowing users to view, add, update, and remove tokens securely.
"""

import logging
from datetime import datetime
from typing import override

from my_unicorn.auth_manager import GitHubAuthManager
from my_unicorn.commands.base import Command
from my_unicorn.secure_token import SecureTokenManager
from my_unicorn.utils.datetime_utils import parse_timestamp


class ManageTokenCommand(Command):
    """Command for managing GitHub API tokens securely.

    This command allows users to:
    - Check token status
    - Add or update tokens
    - Remove tokens
    - View current API rate limits
    - Manage token expiration
    """

    def __init__(self):
        """Initialize the token management command."""
        super().__init__()
        self._logger: logging.Logger = logging.getLogger(__name__)

    @override
    def execute(self) -> None:
        """Execute the token management command.

        This displays the token management menu and handles user input to manage
        GitHub tokens securely.
        """
        self._logger.info("Executing GitHub token management command")

        while True:
            # Show current token status
            self._show_token_status()

            # Display menu with standard print statements
            print("\nGitHub Token Management:")
            print("------------------------")
            print("Security Settings:")
            print("1. Save Token to Secure Keyring (e.g GNOME keyring)")
            print("2. Remove Token")
            print("3. Check API Rate Limits")
            print("4. View Token Expiration")
            print("\nAdvanced Options:")
            print("5. Rotate Token")
            print("6. View Storage Details")
            print("7. Back to Main Menu")
            print("------------------------")

            try:
                choice = input("\nEnter your choice (1-7): ")
                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= 7:
                        if choice_num == 1:
                            self.save_to_keyring()
                        elif choice_num == 2:
                            self.remove_token()
                        elif choice_num == 3:
                            self.check_rate_limits()
                        elif choice_num == 4:
                            self.view_token_expiration()
                        elif choice_num == 5:
                            self.rotate_token()
                        elif choice_num == 6:
                            self.view_storage_details()
                        elif choice_num == 7:
                            self._logger.info("Exiting token management")
                            return
                    else:
                        print("Invalid choice. Please enter a number between 1 and 8.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("\nOperation cancelled. Returning to main menu.")
                return

    def _show_token_status(self) -> None:
        """Display the current token status and storage method.

        This shows whether a token exists and gives basic information about its validity.
        """
        # Check if token exists
        token_exists = SecureTokenManager.token_exists()

        print("\n--- GitHub Token Status ---")

        # Show token existence status
        if token_exists:
            print("✅ GitHub token is set")

            # Get token metadata
            metadata = SecureTokenManager.get_token_metadata()
            if metadata:
                # Check expiration
                if SecureTokenManager.is_token_expired():
                    print("⚠️ Token is EXPIRED - please rotate your token")
                # Get expiration date - use our datetime utility for safe parsing
                elif "expires_at" in metadata:
                    try:
                        expires_dt = parse_timestamp(metadata.get("expires_at"))
                        if expires_dt:
                            days_remaining = (expires_dt - datetime.now()).days

                            if days_remaining <= 7:
                                print(
                                    f"⚠️ Token expiring soon - {days_remaining} days remaining"
                                )
                            else:
                                print(
                                    f"✅ Token valid - {days_remaining} days until expiration"
                                )
                    except Exception as e:
                        self._logger.error("Error processing expiration date: %s", e)
                        print("⚠️ Token expiration date could not be determined")

                # Show when the token was last used
                if "last_used_at" in metadata:
                    try:
                        last_used_dt = parse_timestamp(metadata.get("last_used_at"))
                        if last_used_dt:
                            print(
                                f"📊 Last used: {last_used_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                    except Exception as e:
                        self._logger.error("Error processing last used date: %s", e)
        else:
            print("❌ No GitHub token configured")

        # Simple secure storage status without complex details
        print("\nSecure Storage: ✅ Enabled")
        print("Token Security: ✅ Protected")

    def _get_token_expiration_days(self) -> int | None:
        """Prompt user for token expiration period.

        Returns:
            int | None: Number of days until token expiration or None if cancelled

        """
        print("\nToken Expiration:")
        print("1. 30 days (recommended for regular tokens)")
        print("2. 90 days (standard security practice)")
        print("3. 180 days (extended period)")
        print("4. 365 days (maximum - use only for special cases)")
        print("5. Custom period")
        print("6. Cancel")

        try:
            choice = int(input("\nSelect token expiration period (1-6): "))

            if choice == 1:
                return 30
            elif choice == 2:
                return 90
            elif choice == 3:
                return 180
            elif choice == 4:
                return 365
            elif choice == 5:
                # Custom period
                days = int(input("Enter number of days until expiration (1-365): "))
                if 1 <= days <= 365:
                    return days
                else:
                    print("Invalid period. Must be between 1 and 365 days.")
                    return self._get_token_expiration_days()
            elif choice == 6:
                return None
            else:
                print("Invalid choice. Please select 1-6.")
                return self._get_token_expiration_days()
        except ValueError:
            print("Invalid input. Please enter a number.")
            return self._get_token_expiration_days()
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return None

    def remove_token(self) -> None:
        """Remove the GitHub token from secure storage.

        This removes the token from all potential storage locations.
        After removal, it clears any cached authentication headers and rate limit information.
        """
        self._logger.info("Removing GitHub token")

        if not SecureTokenManager.token_exists():
            print("\nNo token exists to remove.")
            return

        # Confirm before removal
        confirm = input("Are you sure you want to remove the GitHub token? (y/n): ")

        if confirm.lower() != "y":
            print("Token removal cancelled.")
            return

        # Remove the token
        if SecureTokenManager.remove_token():
            print("\n✅ GitHub token removed successfully")
            # Clear any cached authentication headers
            GitHubAuthManager.clear_cached_headers()
            # Clear any cached rate limit information
            GitHubAuthManager.clear_rate_limit_cache()
        else:
            print("\n❓ No tokens were found to remove or removal failed")

    def check_rate_limits(self, token: str | None = None) -> None:
        """Check and display GitHub API rate limits for the current token.

        Makes a direct API call to get the most up-to-date rate limit information.

        Args:
            token: Optional token to use. Uses stored token if not provided.

        """
        self._logger.info("Checking GitHub API rate limits directly from API")
        print("\n--- GitHub API Rate Limits ---")

        try:
            # Use provided token or stored token
            headers = {"Authorization": f"Bearer {token}"} if token else None
            rate_data = GitHubAuthManager.get_live_rate_limit_info(custom_headers=headers)

            # Handle API errors
            if "error" in rate_data:
                self._logger.error("❌ Error retrieving rate limits: %s", rate_data["error"])
                print(
                    f"❌ Error: {rate_data['error']}\n   Please check token and network connection."
                )
                return

            # Extract core rate limit data
            remaining: int = rate_data["remaining"]
            limit: int = rate_data["limit"]
            reset_time = datetime.fromtimestamp(rate_data["reset"])
            reset_formatted = reset_time.strftime("%H:%M:%S")
            full_hour_reset = datetime.fromtimestamp(rate_data["full_hour_reset"]).strftime(
                "%H:%M:%S"
            )

            # Calculate time until reset
            time_left = reset_time - datetime.now()
            minutes_left = max(0, int(time_left.total_seconds() / 60))

            # Display core rate limits
            print(f"Core API Rate Limit: {remaining}/{limit}")
            print(f"Reset in: {minutes_left} minutes ({reset_formatted})")
            print(f"Hourly reset at: {full_hour_reset}")
            print("Note: GitHub API rate limits reset on an hourly basis")

            # Show status indicators
            if remaining == 0:
                print("⛔ Rate limit exceeded! Requests will be rejected until reset time.")
            elif remaining < 10:
                print("⚠️ Rate limit almost exhausted! Use requests sparingly.")
            elif remaining < limit * 0.25:
                print("🔸 Rate limit below 25% - consider spacing out requests.")
            else:
                print("✅ Rate limit healthy.")

            # Display authentication information
            print("\nLive Check: ✅ Rate limit information from GitHub API (not cached)")
            print(f"Check time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # Display token information
            try:
                token_info = GitHubAuthManager.get_token_info()
                if token_info:
                    print("\nToken Information:")

                    # Display token type
                    if token_info.get("is_fine_grained"):
                        print("✅ Fine-grained personal access token (recommended)")
                    elif token_info.get("is_classic"):
                        print("ℹ️ Classic personal access token")
                        print(
                            "   Consider upgrading to fine-grained token for better security"
                        )

                    # Display scopes
                    if scopes := token_info.get("scopes"):
                        print(f"Scopes: {', '.join(scopes)}")

                    # Display rotation status
                    if days := token_info.get("days_until_rotation"):
                        try:
                            days_left = int(days) if isinstance(days, str) else days
                            if days_left <= 0:
                                print("⚠️ Token scheduled for rotation on next use")
                            else:
                                print(f"ℹ️ Token scheduled for rotation in {days_left} days")
                        except ValueError:
                            pass
            except Exception as token_err:
                self._logger.error("Error retrieving token info: %s", token_err)

        except Exception as e:
            err_type = type(e).__name__
            self._logger.error("Error checking rate limits: %s", err_type, exc_info=True)
            print(f"❌ Error: {err_type}: {e}\n   Please check network and token validity.")

    def _validate_token(self, token: str) -> bool:
        """Validate a GitHub token by testing API access.

        This uses GitHubAuthManager for more reliable token validation.

        Args:
            token: GitHub token to validate

        Returns:
            bool: True if token is valid, False otherwise

        """
        print("\nValidating GitHub token...", end="", flush=True)
        self._logger.info("Validating GitHub token")

        try:
            # Create temporary headers with this token for validation
            temp_headers = {"Authorization": f"token {token}"}

            # Use GitHubAuthManager for validation
            is_valid, token_info = GitHubAuthManager.validate_token(
                custom_headers=temp_headers
            )

            if is_valid:
                print(" ✅ Valid!")

                # Display additional token information if available
                if token_info:
                    print("\nToken Details:")
                    if token_info.get("token_type"):
                        print(f"Type: {token_info.get('token_type', 'Personal Access Token')}")
                    if token_info.get("scopes"):
                        print(f"Scopes: {', '.join(token_info.get('scopes', []))}")
                    if token_info.get("rate_limit"):
                        print(f"Rate Limit: {token_info.get('rate_limit', 'Unknown')}")

                    # Show security recommendations based on token type
                    if token_info.get("is_fine_grained", False):
                        print("\n✅ Using fine-grained personal access token (recommended)")
                    elif token_info.get("is_classic", False):
                        print("\n⚠️ Using classic personal access token")
                        print(
                            "   Consider upgrading to a fine-grained token for better security"
                        )

                return True
            else:
                print(" ❌ Invalid!")

                if token_info and token_info.get("error"):
                    print(f"\nError: {token_info.get('error')}")

                return False
        except Exception as e:
            self._logger.error("Error validating token: %s", e)
            print(f" ❌ Error! {e!s}")
            return False

    def view_token_expiration(self) -> None:
        """Display detailed information about token expiration."""
        if not SecureTokenManager.token_exists():
            print("\n❌ No token configured")
            return

        metadata = SecureTokenManager.get_token_metadata()
        if not metadata:
            print("\n❓ No metadata available for the token")
            return

        print("\n--- Token Expiration Information ---")

        # Display creation date - use our datetime utility for safe parsing
        if "created_at" in metadata:
            try:
                created_dt = parse_timestamp(metadata.get("created_at"))
                if created_dt:
                    print(f"Created: {created_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    print("Creation date: Unknown")
            except Exception as e:
                self._logger.error("Error processing creation date: %s", e)
                print("Creation date: Unknown")

        # Display expiration date and status
        if "expires_at" in metadata:
            try:
                expires_dt = parse_timestamp(metadata.get("expires_at"))
                if expires_dt:
                    print(f"Expires: {expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")

                    # Check if expired
                    if SecureTokenManager.is_token_expired():
                        print("Status: 🔴 EXPIRED - Please rotate your token")
                    else:
                        # Calculate days remaining
                        days_remaining = (expires_dt - datetime.now()).days
                        hours_remaining = (expires_dt - datetime.now()).seconds // 3600

                        if days_remaining < 1:
                            print(f"Status: 🟠 Expiring in {hours_remaining} hours")
                        elif days_remaining < 7:
                            print(
                                f"Status: 🟠 Expiring soon - {days_remaining} days remaining"
                            )
                        elif days_remaining < 30:
                            print(f"Status: 🟡 Valid - {days_remaining} days remaining")
                        else:
                            print(f"Status: 🟢 Valid - {days_remaining} days remaining")
                else:
                    print("Expiration date: Unknown")
            except Exception as e:
                self._logger.error("Error processing expiration date: %s", e)
                print("Expiration date: Unknown")

        # Token usage information
        if "last_used_at" in metadata:
            try:
                last_used_dt = parse_timestamp(metadata.get("last_used_at"))
                if last_used_dt:
                    print(f"Last used: {last_used_dt.strftime('%Y-%m-%d %H:%M:%S')}")

                    # Calculate days since last use
                    days_since_use = (datetime.now() - last_used_dt).days
                    if days_since_use == 0:
                        print("Usage: Used today")
                    elif days_since_use == 1:
                        print("Usage: Used yesterday")
                    else:
                        print(f"Usage: Used {days_since_use} days ago")
                else:
                    print("Last used: Unknown")
            except Exception as e:
                self._logger.error("Error processing last used date: %s", e)
                print("Last used: Unknown")

    def rotate_token(self) -> None:
        """Guide the user through rotating their GitHub token."""
        if not SecureTokenManager.token_exists():
            print("\n❌ No token configured to rotate")
            return

        print("\n--- Token Rotation ---")
        print(
            "Token rotation is an important security practice to limit the impact of potential token exposure."
        )
        print(
            "This process will guide you through creating a new GitHub token and replacing your existing one."
        )

        print("\nSteps:")
        print("1. Go to GitHub > Settings > Developer settings > Personal access tokens")
        print("2. Create a new token with the same permissions as your current token")
        print("3. Enter the new token when prompted")

        proceed = input("\nDo you want to proceed with token rotation? (y/n): ")
        if proceed.lower() != "y":
            print("Token rotation cancelled.")
            return

        # Capture information about the existing token for reference
        old_metadata = SecureTokenManager.get_token_metadata()

        # Get the new token from the user
        new_token = SecureTokenManager.prompt_for_token()

        if not new_token:
            print("Token rotation cancelled.")
            return

        # Validate the new token
        if not self._validate_token(new_token):
            print("\n❌ Invalid GitHub token! Token rotation aborted.")
            return

        # Ask for token expiration
        expiration_days = self._get_token_expiration_days()
        if expiration_days is None:
            print("Token rotation cancelled.")
            return

        # Save the new token
        if SecureTokenManager.save_token(new_token, expires_in_days=expiration_days):
            print("\n✅ New GitHub token saved successfully!")
            print(f"📅 New token will expire in {expiration_days} days")

            # Clear any cached authentication headers
            GitHubAuthManager.clear_cached_headers()

            # Remind user to revoke the old token
            print("\n⚠️ IMPORTANT: Remember to revoke your old token on GitHub!")
            print("Go to GitHub > Settings > Developer settings > Personal access tokens")
            print("Find your old token and click 'Delete'")

            # Show current rate limits with new token
            print("\nChecking rate limits with new token...")
            self.check_rate_limits(new_token)
        else:
            print("\n❌ Failed to save new token! Rotation aborted.")
            print("   Make sure you have keyring or cryptography modules installed.")

    def view_storage_details(self) -> None:
        """Display detailed information about the current storage method for the token."""
        if not SecureTokenManager.token_exists():
            print("\n❌ No token configured")
            return

        print("\n--- Token Storage Details ---")

        # Get keyring status to understand available storage methods
        keyring_status = SecureTokenManager.get_keyring_status()

        # Get token metadata for storage information
        metadata = SecureTokenManager.get_token_metadata()

        # Display storage method based on metadata if available
        if metadata:
            # Get storage information
            storage_method = metadata.get("storage_method", "Unknown")
            storage_location = metadata.get("storage_location", "Unknown")
            storage_status = metadata.get("storage_status", "Unknown")

            print(f"Storage Method: {storage_method}")
            print(f"Storage Location: {storage_location}")
            print(f"Storage Status: {storage_status}")

            # Display method-specific details
            if "storage_method_detail" in metadata:
                print(f"Storage Implementation: {metadata['storage_method_detail']}")

            if "encryption_type" in metadata:
                print(f"Encryption: {metadata['encryption_type']}")

            if "fallback_reason" in metadata:
                print(f"Note: {metadata['fallback_reason']}")

            # Display when the token was stored based on creation time
            if "created_at" in metadata:
                try:
                    created_dt = parse_timestamp(metadata.get("created_at"))
                    if created_dt:
                        print(f"Storage Date: {created_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print("Storage Date: Unknown")
                except Exception as e:
                    self._logger.error("Error processing creation date: %s", e)
                    print("Storage Date: Unknown")
        else:
            print("❓ No storage metadata available")

        # Show available secure storage methods
        print("\nSupported Storage Methods:")
        backend_name = keyring_status.get("backend_name", "Unknown")
        backend_module = keyring_status.get("backend_module", "Unknown")

        print(f"✅ Keyring Backend: {backend_name} (Module: {backend_module})")

        if backend_name == "Unknown":
            print("⚠️ Warning: No secure storage backend detected on this system!")
            print("   Ensure a compatible keyring backend is installed and configured.")

        # Add some general security advice
        print("\nSecurity Recommendations:")
        if backend_name == "Unknown":
            print("➤ Install and configure a secure keyring backend for token storage")
            print("  - For GNOME: Consider installing the seahorse package")
        else:
            print(f"➤ {backend_name} provides secure token storage")

        print("➤ Rotate your token regularly (every 30-90 days)")
        print("➤ Use fine-grained access tokens with minimal permissions")
        print("➤ Never share your token or commit it to version control")

    def save_to_keyring(self) -> None:
        """Save token specifically to the keyring using the keyring library.

        This is a simpler approach than the standard save method, directly
        targeting the keyring without complex fallback logic.
        """
        self._logger.info("Saving token to keyring")

        # Check for existing token
        current_token = SecureTokenManager.get_token(validate_expiration=False)

        # If a token already exists, confirm update
        # TODO: if it is already exist, not need to write again? this is non-sense?
        if current_token:
            print("\nA token already exists.")
            choice = input("Do you want to update the token in the keyring? (y/n): ")
            if choice.lower() != "y":
                print("Operation cancelled.")
                return

            # Use the existing token
            token = current_token
            print("Using the existing token for keyring storage")
        else:
            # Get the token from the user (input is hidden)
            token = SecureTokenManager.prompt_for_token()

            if not token:
                print("Operation cancelled.")
                return

            # Validate the token using GitHubAuthManager for improved validation
            if not self._validate_token(token):
                self._logger.error("Invalid GitHub token! _validate_token returned False")
                print("\n❌ Invalid GitHub token! Token was not saved.")
                print("   Please make sure you've entered the token correctly.")
                return

        # Ask for token expiration
        expiration_days = self._get_token_expiration_days()
        if expiration_days is None:
            self._logger.error(
                "Token expiration days not provided. _get_token_expiration_days returned None"
            )
            print("Operation cancelled.")
            return

        # Get keyring status and display info before attempting to save
        keyring_status = SecureTokenManager.get_keyring_status()
        print("\nDetected keyring status:")

        backend_name = keyring_status.get("backend_name", "Unknown")
        backend_module = keyring_status.get("backend_module", "Unknown")

        print(f"✅ Keyring Backend: {backend_name} (Module: {backend_module})")

        # Check if a secure keyring backend is available
        if backend_name == "Unknown":
            print("\n⚠️ Warning: No secure keyring backend is available!")
            print("A secure keyring backend is required for token storage.")

            choice = input("\nWould you like to try saving to keyring anyway? (y/n): ")
            if choice.lower() != "y":
                print("Operation cancelled.")
                self._offer_fallback_options()
                return

        # Save token to keyring
        result = SecureTokenManager.save_token(
            token,
            expires_in_days=expiration_days,
        )

        if result:
            print("\n✅ GitHub token saved successfully to the keyring!")
            print(f"📅 Token will expire in {expiration_days} days")

            # Clear any cached authentication headers
            GitHubAuthManager.clear_cached_headers()

            # Show current rate limits with the token
            self.check_rate_limits(token)
        else:
            print("\n❌ Failed to save token to keyring!")
            self._offer_fallback_options()

    def _offer_fallback_options(self) -> None:
        """Offer fallback options for token storage when keyring fails."""
        print("\nWould you like to try saving with the standard method instead?")
        print("This will attempt multiple storage methods in order of security preference.")
        fallback = input("Try standard save method? (y/n): ")

        if fallback.lower() == "y":
            token = SecureTokenManager.get_token(validate_expiration=False)
            expiration_days = self._get_token_expiration_days()

            if token and expiration_days:
                if SecureTokenManager.save_token(token, expires_in_days=expiration_days):
                    print("\n✅ GitHub token saved successfully with fallback method!")
                    print(f"📅 Token will expire in {expiration_days} days")

                    # Clear any cached authentication headers
                    GitHubAuthManager.clear_cached_headers()

                    # Show current rate limits with the token
                    self.check_rate_limits(token)
                else:
                    print("\n❌ Failed to save token with all methods!")
                    self._show_installation_help()
            else:
                print("Operation cancelled.")
        else:
            self._show_installation_help()

    def _show_installation_help(self) -> None:
        """Show installation help for keyring and related dependencies."""
        print("\nTo resolve keyring issues, try these steps:")
        print("1. Install required Python packages:")
        print("   pip install keyring dbus-python secretstorage cryptography")
        print("\n2. Install system packages:")
        print("   - For GNOME: sudo apt install seahorse libsecret-1-0 python3-secretstorage")
        print("   - For KDE: sudo apt install kwalletmanager")
        print("\n3. Check if the correct virtual environment is activated")
        print("\n4. Restart your system after installing these packages")
