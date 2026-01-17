"""Token command handler for my-unicorn CLI.

This module handles GitHub token management operations, including saving and
removing tokens from the keyring-based secure storage.
"""

import getpass
import sys
from argparse import Namespace

import keyring

from my_unicorn.core.auth import (
    MAX_TOKEN_LENGTH,
    _scrub_token,
    validate_github_token,
)
from my_unicorn.logger import get_logger

from .base import BaseCommandHandler

logger = get_logger(__name__)


class TokenHandler(BaseCommandHandler):
    """Handler for token command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the token command."""
        if args.save:
            logger.info("Saving GitHub token...")
            await self._save_token()
        elif args.remove:
            logger.info("Removing GitHub token...")
            await self._remove_token()

    async def _save_token(self) -> None:
        """Save GitHub authentication token.

        Prompts the user to enter and confirm a token, validates the token's
        format, and stores it using the configured token storage backend.

        Raises:
            ValueError: If the input is empty, the confirmation does not match,
                or the token format is invalid.
            Exception: Re-raises underlying storage errors or other issues.

        """
        token = ""
        confirm_token = ""
        try:
            # Prompt for token and confirmation
            token, confirm_token = self._prompt_for_token()

            # Validate confirmation matches and token is valid
            self._validate_token_confirmation(token, confirm_token)

            # Save to token store via auth manager's token store
            self.auth_manager.token_store.set(token)
            logger.info("GitHub token saved successfully.")

            # Security: Scrub tokens from memory after successful save
            _scrub_token(token)
            _scrub_token(confirm_token)

        except (EOFError, KeyboardInterrupt):
            logger.error("Token input aborted by user")  # noqa: TRY400
            # Security: Scrub tokens from memory on abort
            _scrub_token(token)
            _scrub_token(confirm_token)
            sys.exit(1)
        except ValueError as e:
            # Scrub tokens and provide user-friendly error
            _scrub_token(token)
            _scrub_token(confirm_token)
            logger.error(str(e))  # noqa: TRY400
            sys.exit(1)
        except Exception:
            # Handle storage errors with sanitized messages
            self._handle_storage_error(token, confirm_token)
            raise

    async def _remove_token(self) -> None:
        """Remove the stored GitHub token from the token store.

        Handles the case where no token exists gracefully.

        """
        try:
            self.auth_manager.token_store.delete()
            logger.info("GitHub token removed from keyring.")
        except keyring.errors.PasswordDeleteError:
            # No token stored - provide friendly message
            logger.warning("No GitHub token found in keyring.")
            logger.info(
                "Tip: Use 'my-unicorn token --save' to save a token first."
            )
        except Exception:
            # Security: Sanitize error message to prevent information
            # disclosure (already logged by token store)
            logger.exception("Failed to remove token from storage")
            raise

    @staticmethod
    def _prompt_for_token() -> tuple[str, str]:
        """Prompt user for token input and confirmation.

        Returns:
            tuple[str, str]: Token and confirmation token.

        Raises:
            ValueError: If input is empty or aborted.
            EOFError: If input is aborted.
            KeyboardInterrupt: If input is interrupted.

        """
        token: str = getpass.getpass(
            prompt="Enter your GitHub token (input hidden): "
        )
        if token is None:
            logger.error("No input received for GitHub token")
            msg = "Token cannot be empty"
            raise ValueError(msg)

        token = token.strip()
        if not token:
            logger.error("Token input is empty")
            msg = "Token cannot be empty"
            raise ValueError(msg)

        # Security: Validate maximum token length to prevent memory exhaustion
        if len(token) > MAX_TOKEN_LENGTH:
            logger.error("Token exceeds maximum allowed length")
            _scrub_token(token)
            msg = (
                f"Token exceeds maximum allowed length "
                f"({MAX_TOKEN_LENGTH} characters)"
            )
            raise ValueError(msg)

        # Confirm token input
        confirm_token: str = getpass.getpass(
            prompt="Confirm your GitHub token: "
        )
        if confirm_token is None:
            logger.error("No input received for GitHub token confirmation")
            msg = "Token confirmation does not match"
            raise ValueError(msg)

        confirm_token = confirm_token.strip()
        return token, confirm_token

    @staticmethod
    def _validate_token_confirmation(token: str, confirm_token: str) -> None:
        """Validate token confirmation matches original token.

        Args:
            token: Original token.
            confirm_token: Confirmation token.

        Raises:
            ValueError: If tokens don't match or validation fails.

        """
        if token != confirm_token:
            logger.error("Token confirmation mismatch")
            # Security: Scrub tokens from memory on failure
            _scrub_token(token)
            _scrub_token(confirm_token)
            msg = "Token confirmation does not match"
            raise ValueError(msg)

        # Validate token format before saving
        if not validate_github_token(token):
            logger.error("Token validation failed")
            # Security: Scrub token from memory on validation failure
            _scrub_token(token)
            _scrub_token(confirm_token)
            msg = (
                "Invalid GitHub token format. "
                "Must be a valid GitHub token (classic or fine-grained PAT)."
            )
            raise ValueError(msg)

    def _handle_storage_error(self, token: str, confirm_token: str) -> None:
        """Handle token storage errors with sanitized error messages.

        Args:
            token: The token to scrub.
            confirm_token: The confirmation token to scrub.

        """
        # Security: Scrub tokens from memory on any exception
        _scrub_token(token)
        _scrub_token(confirm_token)

        # Errors are already logged by the token store implementation
        # No need to log again here
