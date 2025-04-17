#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub token management command module.

This module provides the command implementation for managing GitHub API tokens,
allowing users to view, add, update, and remove tokens securely.
"""

import logging
import sys
from typing import Dict, Any

import requests

from commands.command import Command
from src.secure_token import SecureTokenManager


class ManageTokenCommand(Command):
    """
    Command for managing GitHub API tokens securely.

    This command allows users to:
    - Check token status
    - Add or update tokens
    - Remove tokens
    - View current API rate limits
    """

    def __init__(self):
        """Initialize the token management command."""
        self._logger = logging.getLogger(__name__)

    def execute(self) -> None:
        """
        Execute the token management command.

        This displays the token management menu and handles user input to manage
        GitHub tokens securely.
        """
        self._logger.info("Executing GitHub token management command")

        while True:
            # Show current token status
            self._show_token_status()

            # Display menu
            print("\nGitHub Token Management:")
            print("------------------------")
            print("1. Add or Update Token")
            print("2. Remove Token")
            print("3. Check API Rate Limits")
            print("4. Back to Main Menu")

            try:
                choice = int(input("\nEnter your choice (1-4): "))

                if choice == 1:
                    self._add_update_token()
                elif choice == 2:
                    self._remove_token()
                elif choice == 3:
                    self._check_rate_limits()
                elif choice == 4:
                    self._logger.info("Exiting token management")
                    return
                else:
                    print("Invalid choice. Please enter a number between 1 and 4.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("\nOperation cancelled. Returning to main menu.")
                return

    def _show_token_status(self) -> None:
        """
        Display the current token status and storage method.

        This shows whether a token exists and which secure storage method is being used.
        """
        # Get keyring status to understand available secure storage methods
        keyring_status = SecureTokenManager.get_keyring_status()

        # Check if token exists
        token_exists = SecureTokenManager.token_exists()

        print("\n--- GitHub Token Status ---")

        # Show token existence status
        if token_exists:
            print("✅ GitHub token is set")
        else:
            print("❌ No GitHub token configured")

        # Show available secure storage methods
        print("\nSecure Storage Status:")
        if keyring_status["gnome_keyring_available"]:
            print("✅ Seahorse/GNOME keyring available (primary)")
        else:
            print("❌ Seahorse/GNOME keyring not available")

        if keyring_status["kde_wallet_available"]:
            if keyring_status["gnome_keyring_available"]:
                print("✅ KDE Wallet available (fallback)")
            else:
                print("✅ KDE Wallet available (primary)")
        else:
            print("❌ KDE Wallet not available")

        if not keyring_status["any_keyring_available"] and keyring_status["crypto_available"]:
            print("✅ Encrypted file storage available (fallback)")
        elif keyring_status["crypto_available"]:
            print("✅ Encrypted file storage available (secondary fallback)")
        else:
            print("❌ Encrypted file storage not available")

        if not keyring_status["any_keyring_available"] and not keyring_status["crypto_available"]:
            print("\n⚠️ Warning: No secure storage methods available!")
            print("   Please install python-keyring or python-cryptography packages.")

    def _add_update_token(self) -> None:
        """
        Add or update a GitHub token in the secure storage.

        This prompts the user for a token and validates it before saving.
        """
        self._logger.info("Adding/updating GitHub token")

        # Get the token from the user (input is hidden)
        token = SecureTokenManager.prompt_for_token()

        if not token:
            print("Operation cancelled.")
            return

        # Validate the token
        if self._validate_token(token):
            # Save the token securely
            if SecureTokenManager.save_token(token):
                print("\n✅ GitHub token saved successfully!")
                # Show current rate limits with new token
                self._check_rate_limits(token)
            else:
                print("\n❌ Failed to save token securely!")
                print("   Make sure you have keyring or cryptography modules installed.")
        else:
            print("\n❌ Invalid GitHub token! Token was not saved.")
            print("   Please make sure you've entered the token correctly.")

    def _remove_token(self) -> None:
        """
        Remove the GitHub token from secure storage.

        This removes the token from all potential storage locations.
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
        else:
            print("\n❓ No tokens were found to remove or removal failed")

    def _check_rate_limits(self, token: str = None) -> None:
        """
        Check the current GitHub API rate limits.

        This shows the rate limits for the current token or an provided token.

        Args:
            token: Optional token to use for checking rate limits
        """
        self._logger.info("Checking GitHub API rate limits")

        # Use provided token or get from secure storage
        if not token:
            token = SecureTokenManager.get_token()

        # Prepare request headers
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            # Add token to headers but don't log the actual token value
            headers["Authorization"] = f"Bearer {token}"
            self._logger.info("Using token from secure storage for rate limit check")
        else:
            self._logger.info("No token available, checking unauthenticated rate limits")

        try:
            # Check rate limit
            response = requests.get(
                "https://api.github.com/rate_limit", headers=headers, timeout=10
            )
            response.raise_for_status()

            # Parse rate limit data
            data = response.json()
            rate = data.get("rate", {})

            remaining = rate.get("remaining", 0)
            limit = rate.get("limit", 0)
            reset_time = rate.get("reset", 0)

            # Format reset time
            from datetime import datetime

            reset_datetime = datetime.fromtimestamp(reset_time)
            reset_formatted = reset_datetime.strftime("%Y-%m-%d %H:%M:%S")

            # Display rate limit information
            print("\n--- GitHub API Rate Limits ---")
            print(f"Remaining requests: {remaining}/{limit}")
            print(f"Resets at: {reset_formatted}")

            # Show authenticated status
            if token:
                print("Status: Authenticated")

                # Show additional rate limit info for authenticated users
                if "resources" in data:
                    resources = data["resources"]
                    if "graphql" in resources:
                        graphql = resources["graphql"]
                        print(
                            f"GraphQL API: {graphql.get('remaining', 0)}/{graphql.get('limit', 0)}"
                        )
                    if "search" in resources:
                        search = resources["search"]
                        print(f"Search API: {search.get('remaining', 0)}/{search.get('limit', 0)}")
            else:
                print("Status: Unauthenticated (limited to 60 requests/hour)")
                if remaining < 20:
                    print("⚠️ Low on unauthenticated requests! Consider adding a token.")

            # Show warning if rate limit is low
            if token and remaining < 100:
                print("⚠️ Running low on API requests!")

        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error checking rate limits: {e}")
            self._logger.error(f"Rate limit check failed: {e}")

            # Ensure no token is exposed in error messages
            safe_error = str(e).replace(token, "***TOKEN***") if token else str(e)
            self._logger.error(f"Rate limit check failed: {safe_error}")

    def _validate_token(self, token: str) -> bool:
        """
        Validate a GitHub token by testing it with the API.

        Args:
            token: The GitHub token to validate

        Returns:
            bool: True if the token is valid, False otherwise
        """
        if not token:
            return False

        try:
            # Make a simple authenticated request
            response = requests.get(
                "https://api.github.com/rate_limit",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=10,
            )

            # Check if authentication succeeded
            if response.status_code == 200:
                return True

            if response.status_code == 401:
                self._logger.warning("Token validation failed: Invalid credentials")
                print("Authentication failed: Invalid token")
                return False

            self._logger.warning(f"Token validation failed: Status {response.status_code}")
            print(f"Unexpected response: {response.status_code}")
            return False

        except requests.exceptions.RequestException as e:
            self._logger.error(f"Token validation request failed: {e}")
            print(f"Connection error: {e}")
            return False
