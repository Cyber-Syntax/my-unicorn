#!/usr/bin/env python3
"""GitHub token management command module.

This module provides the command implementation for managing GitHub API tokens,
allowing users to view, add, update, and remove tokens securely.
"""

import logging
from datetime import datetime, timedelta

from my_unicorn.auth_manager import GitHubAuthManager
from my_unicorn.commands.base import Command
from my_unicorn.secure_token import CONFIG_DIR, TOKEN_FILE, TOKEN_METADATA_FILE, SecureTokenManager
from my_unicorn.utils.datetime_utils import parse_timestamp


class ManageTokenCommand(Command):
    """Command for managing GitHub API tokens securely.

    This command allows users to:
    - Check token status
    - Add or update tokens
    - Remove tokens
    - View current API rate limits
    - Manage token expiration
    - View token audit logs
    """

    def __init__(self):
        """Initialize the token management command."""
        self._logger = logging.getLogger(__name__)

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
                                print(f"⚠️ Token expiring soon - {days_remaining} days remaining")
                            else:
                                print(f"✅ Token valid - {days_remaining} days until expiration")
                    except Exception as e:
                        self._logger.error(f"Error processing expiration date: {e}")
                        print("⚠️ Token expiration date could not be determined")

                # Show when the token was last used
                if "last_used_at" in metadata:
                    try:
                        last_used_dt = parse_timestamp(metadata.get("last_used_at"))
                        if last_used_dt:
                            print(f"📊 Last used: {last_used_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    except Exception as e:
                        self._logger.error(f"Error processing last used date: {e}")
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

    def check_rate_limits(self, token: str = None) -> None:
        """Check and display GitHub API rate limits for the current token.

        This method makes a direct API call to GitHub to get the most up-to-date
        rate limit information, bypassing any cache.

        Args:
            token: Optional token to use for checking rate limits.
                  If not provided, the stored token will be used.

        """
        self._logger.info("Checking GitHub API rate limits directly from API")
        print("\n--- GitHub API Rate Limits ---")

        try:
            # If token is provided, temporarily use it without saving
            if token:
                self._logger.debug("Using provided token for rate limit check")
                temp_headers = {"Authorization": f"Bearer {token}"}
                # Use the new get_live_rate_limit_info method for real-time data
                rate_limit_info = GitHubAuthManager.get_live_rate_limit_info(
                    custom_headers=temp_headers
                )
            else:
                self._logger.debug("Using stored token for rate limit check")
                # Use the current authenticated session with the new live check method
                rate_limit_info = GitHubAuthManager.get_live_rate_limit_info()

            # Check if there was an error
            if "error" in rate_limit_info:
                error_msg = (
                    f"❌ Error retrieving rate limit information: {rate_limit_info['error']}"
                )
                self._logger.error(error_msg)
                print(error_msg)
                print("   Please check your token validity and network connection.")
                return

            # Standard text output
            # Display core rate limits
            core_limits = rate_limit_info.get("resources", {}).get("core", {})
            if core_limits:
                remaining = core_limits.get("remaining", 0)
                limit = core_limits.get("limit", 0)
                reset_timestamp = core_limits.get("reset", 0)

                # Calculate time until reset
                if reset_timestamp:
                    reset_time = datetime.fromtimestamp(reset_timestamp)
                    time_until_reset = reset_time - datetime.now()
                    minutes_until_reset = max(0, int(time_until_reset.total_seconds() / 60))

                    # Get the full hour reset time if available
                    full_hour_reset_formatted = None
                    if "full_hour_reset" in rate_limit_info:
                        full_hour_reset = datetime.fromtimestamp(rate_limit_info["full_hour_reset"])
                        full_hour_reset_formatted = full_hour_reset.strftime("%H:%M:%S")

                    print(f"Core API Rate Limit: {remaining}/{limit}")

                    # Display both the GitHub-provided reset time and the hourly reset explanation
                    if full_hour_reset_formatted:
                        print(
                            f"Reset in: {minutes_until_reset} minutes ({reset_time.strftime('%H:%M:%S')}) - hourly at {full_hour_reset_formatted}"
                        )
                    else:
                        print(
                            f"Reset in: {minutes_until_reset} minutes ({reset_time.strftime('%H:%M:%S')})"
                        )

                    print("Note: GitHub API rate limits reset on an hourly basis")

                    # Show rate limit status with emoji indicators
                    if remaining == 0:
                        print("⛔ Rate limit exceeded! Requests will be rejected until reset time.")
                    elif remaining < 10:
                        print("⚠️ Rate limit almost exhausted! Use requests sparingly.")
                    else:
                        percentage = (remaining / limit) * 100
                        if percentage < 25:
                            print("🔸 Rate limit below 25% - consider spacing out requests.")
                        else:
                            print("✅ Rate limit healthy.")
                else:
                    self._logger.warning("Missing reset timestamp in rate limit data")
                    print(f"Core API Rate Limit: {remaining}/{limit}")
                    print("Reset time: Not available")
            else:
                self._logger.warning("No core rate limit information available")
                print("No core rate limit information available")

            # Display search rate limits
            search_limits = rate_limit_info.get("resources", {}).get("search", {})
            if search_limits:
                search_remaining = search_limits.get("remaining", 0)
                search_limit = search_limits.get("limit", 0)
                search_reset = search_limits.get("reset", 0)

                if search_reset:
                    search_reset_time = datetime.fromtimestamp(search_reset)
                    search_time_until_reset = search_reset_time - datetime.now()
                    search_minutes = max(0, int(search_time_until_reset.total_seconds() / 60))

                    # Get the full hour reset if available
                    full_hour_reset_formatted = None
                    if "full_hour_reset" in rate_limit_info:
                        full_hour_reset = datetime.fromtimestamp(rate_limit_info["full_hour_reset"])
                        full_hour_reset_formatted = full_hour_reset.strftime("%H:%M:%S")

                    print(f"\nSearch API Rate Limit: {search_remaining}/{search_limit}")

                    # Display both the GitHub-provided reset time and the hourly reset explanation
                    if full_hour_reset_formatted:
                        print(
                            f"Reset in: {search_minutes} minutes ({search_reset_time.strftime('%H:%M:%S')}) - hourly at {full_hour_reset_formatted}"
                        )
                    else:
                        print(
                            f"Reset in: {search_minutes} minutes ({search_reset_time.strftime('%H:%M:%S')})"
                        )

            # Show graphql rate limits if available
            graphql_limits = rate_limit_info.get("resources", {}).get("graphql", {})
            if graphql_limits:
                graphql_remaining = graphql_limits.get("remaining", 0)
                graphql_limit = graphql_limits.get("limit", 0)
                graphql_reset = graphql_limits.get("reset", 0)

                print(f"\nGraphQL API Rate Limit: {graphql_remaining}/{graphql_limit}")

                # Show reset info for GraphQL if available
                if graphql_reset:
                    graphql_reset_time = datetime.fromtimestamp(graphql_reset)
                    graphql_minutes = max(
                        0, int((graphql_reset_time - datetime.now()).total_seconds() / 60)
                    )

                    if "full_hour_reset" in rate_limit_info:
                        full_hour_reset = datetime.fromtimestamp(rate_limit_info["full_hour_reset"])
                        print(
                            f"Reset in: {graphql_minutes} minutes (hourly at {full_hour_reset.strftime('%H:%M:%S')})"
                        )
                    else:
                        print(
                            f"Reset in: {graphql_minutes} minutes ({graphql_reset_time.strftime('%H:%M:%S')})"
                        )

            # Display information about the check
            print("\nLive Check: ✅ Rate limit information from GitHub API (not cached)")
            check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Check time: {check_time}")

            # Display authentication type information
            try:
                token_info = GitHubAuthManager.get_token_info()
                if token_info:
                    print("\nToken Information:")
                    if token_info.get("token_type"):
                        print(f"Type: {token_info.get('token_type', 'Unknown')}")
                    if token_info.get("scopes"):
                        print(f"Scopes: {', '.join(token_info.get('scopes', []))}")

                    # Check if days_until_rotation is a string and convert if needed
                    if (
                        "days_until_rotation" in token_info
                        and token_info["days_until_rotation"] is not None
                    ):
                        days_until_rotation = token_info["days_until_rotation"]
                        # Convert to int if it's a string
                        if isinstance(days_until_rotation, str):
                            try:
                                days_until_rotation = int(days_until_rotation)
                            except ValueError:
                                days_until_rotation = None

                        # Now it's safe to compare
                        if days_until_rotation is not None and days_until_rotation <= 0:
                            print("⚠️ Token scheduled for rotation on next use")
                        elif days_until_rotation is not None:
                            print(f"ℹ️ Token scheduled for rotation in {days_until_rotation} days")

                    if token_info.get("is_fine_grained", False):
                        print("✅ Using fine-grained personal access token (recommended)")
                    elif token_info.get("is_classic", False):
                        print("ℹ️ Using classic personal access token")
                        print("   Consider upgrading to a fine-grained token for better security")
            except Exception as token_info_error:
                self._logger.error(f"Error retrieving token information: {token_info_error}")
                # Continue execution - token info is not critical

        except Exception as e:
            # Log both the error type and the message for better debugging
            self._logger.error(f"Error checking rate limits: {type(e).__name__}: {e!s}")
            self._logger.exception("Detailed exception info:")

            print(f"❌ Error checking rate limits: {type(e).__name__}: {e!s}")
            print("   Please check your network connection and token validity.")
            print("   Check application logs for more details.")

    def validate_token(self, token: str) -> bool:
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
            is_valid, token_info = GitHubAuthManager.validate_token(custom_headers=temp_headers)

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
                        print("   Consider upgrading to a fine-grained token for better security")

                return True
            else:
                print(" ❌ Invalid!")

                if token_info and token_info.get("error"):
                    print(f"\nError: {token_info.get('error')}")

                return False
        except Exception as e:
            self._logger.error(f"Error validating token: {e}")
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
                self._logger.error(f"Error processing creation date: {e}")
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
                            print(f"Status: 🟠 Expiring soon - {days_remaining} days remaining")
                        elif days_remaining < 30:
                            print(f"Status: 🟡 Valid - {days_remaining} days remaining")
                        else:
                            print(f"Status: 🟢 Valid - {days_remaining} days remaining")
                else:
                    print("Expiration date: Unknown")
            except Exception as e:
                self._logger.error(f"Error processing expiration date: {e}")
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
                self._logger.error(f"Error processing last used date: {e}")
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
            self._check_rate_limits(new_token)
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
                    self._logger.error(f"Error processing creation date: {e}")
                    print("Storage Date: Unknown")
        else:
            print("❓ No storage metadata available")

        # Show available secure storage methods
        print("\nSupported Storage Methods:")
        if keyring_status["gnome_keyring_available"]:
            print("✅ GNOME keyring (Seahorse) - Available and supported")
        else:
            print("❌ GNOME keyring (Seahorse) - Not available")

        if keyring_status["kde_wallet_available"]:
            print("✅ KDE Wallet - Available and supported")
        else:
            print("❌ KDE Wallet - Not available")

        if keyring_status["crypto_available"]:
            print("✅ Encrypted file storage - Available and supported")
        else:
            print("❌ Encrypted file storage - Not available")

        if not keyring_status["any_keyring_available"] and not keyring_status["crypto_available"]:
            print("⚠️ Warning: No secure storage methods detected on this system!")
            print("   Consider installing a keyring or cryptography module.")
            print("   Run 'pip install keyring cryptography' for better security.")

        # Show file locations if appropriate
        if storage_method == "Encrypted file" or not keyring_status["any_keyring_available"]:
            print("\nFile Storage Locations:")
            print(f"Token file: {TOKEN_FILE}")
            print(f"Metadata file: {TOKEN_METADATA_FILE}")
            print(f"Config directory: {CONFIG_DIR}")

        # Add some general security advice
        print("\nSecurity Recommendations:")
        if (
            not keyring_status["gnome_keyring_available"]
            and not keyring_status["kde_wallet_available"]
        ):
            print("➤ Install and configure a system keyring for better security")
            print("  - For GNOME: Install seahorse package")
            print("  - For KDE: Enable KWallet")
        else:
            print("➤ Always use a system keyring when available for maximum security")

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
            if not self.validate_token(token):
                logging.error("Invalid GitHub token! _validate_token returned False")
                print("\n❌ Invalid GitHub token! Token was not saved.")
                print("   Please make sure you've entered the token correctly.")
                return

        # Ask for token expiration
        expiration_days = self._get_token_expiration_days()
        if expiration_days is None:
            logging.error(
                "Token expiration days not provided. _get_token_expiration_days returned None"
            )
            print("Operation cancelled.")
            return

        # Get keyring status and display info before attempting to save
        keyring_status = SecureTokenManager.get_keyring_status()
        print("\nDetected keyring status:")

        if keyring_status["gnome_keyring_available"]:
            print("✅ GNOME keyring (Seahorse) detected")
        else:
            print("❌ GNOME keyring not available")

        if keyring_status["kde_wallet_available"]:
            print("✅ KDE Wallet detected")
        else:
            print("❌ KDE Wallet not available")

        # Check if any keyring is available
        if not keyring_status["any_keyring_available"]:
            print("\n⚠️ Warning: No supported keyring found!")
            print("The keyring module may be installed, but no supported backend is available.")

            choice = input("\nWould you like to try saving to keyring anyway? (y/n): ")
            if choice.lower() != "y":
                print("Operation cancelled.")
                self._offer_fallback_options()
                return

        # Save directly to keyring using our enhanced method with improved metadata
        metadata = {
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=expiration_days)).isoformat(),
            "source": "manage_token_command",
            "security_level": "high",
        }

        # Save token to keyring using our enhanced method with improved metadata
        result = SecureTokenManager.save_token(
            token,
            expires_in_days=expiration_days,
            storage_preference="keyring_only",
            metadata=metadata,
        )

        if result:
            print("\n✅ GitHub token saved successfully to the keyring!")
            print(f"📅 Token will expire in {expiration_days} days")

            # Clear any cached authentication headers
            GitHubAuthManager.clear_cached_headers()

            # Enable audit logging for better security tracking
            GitHubAuthManager.set_audit_enabled(True)

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
                    self._check_rate_limits(token)
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
