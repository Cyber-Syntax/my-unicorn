"""Version command for my-unicorn CLI."""

import argparse
import logging
import sys
from pathlib import Path

from my_unicorn.commands.base import Command
from my_unicorn.update import check_for_update, display_current_version, perform_update

logger = logging.getLogger(__name__)


class VersionCommand(Command):
    """Handle version-related operations."""

    def __init__(self) -> None:
        """Initialize the version command."""
        super().__init__()
        self._args: argparse.Namespace | None = None

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add arguments specific to version command.

        Args:
            parser: The argument parser to add arguments to

        """
        version_group = parser.add_mutually_exclusive_group()
        version_group.add_argument(
            "--check", action="store_true", help="Check for available updates"
        )
        version_group.add_argument(
            "--update", action="store_true", help="Update to the latest version"
        )
        parser.add_argument(
            "--update-dir",
            type=Path,
            help="Custom directory for update process (default: ~/.cache/my-unicorn-update)",
        )

    def set_args(self, args: argparse.Namespace) -> None:
        """Set the parsed arguments for this command.

        Args:
            args: Parsed command line arguments

        """
        self._args = args

    def execute(self) -> None:
        """Execute the version command."""
        if self._args is None:
            # Interactive mode - just show version
            display_current_version()
            return

        if hasattr(self._args, "check") and self._args.check:
            self._handle_check_update()
        elif hasattr(self._args, "update") and self._args.update:
            update_dir = getattr(self._args, "update_dir", None)
            self._handle_update(update_dir)
        else:
            # Default behavior - show version
            display_current_version()

    def _handle_check_update(self) -> None:
        """Handle checking for updates."""
        logger.info("Checking for updates...")
        try:
            has_update = check_for_update()
            if has_update:
                print("\nRun 'my-unicorn version --update' to update to the latest version.")
            sys.exit(0 if not has_update else 1)  # Exit code 1 if update available
        except Exception as e:
            logger.error("Error checking for updates: %s", e)
            print(f"Error checking for updates: {e}")
            sys.exit(2)

    def _handle_update(self, custom_dir: Path | None = None) -> None:
        """Handle performing the update.

        Args:
            custom_dir: Custom directory for update process

        """
        logger.info("Starting update process...")

        # First check if update is available
        if not check_for_update():
            print("No updates available.")
            return

        # Confirm with user
        response = input("Do you want to proceed with the update? (y/N): ")
        if response.lower() not in ("y", "yes"):
            print("Update cancelled.")
            return

        # Perform the update
        try:
            success = perform_update()
            if success:
                print("Update completed successfully!")
                print(
                    "Please restart your terminal or run 'source ~/.zshrc' to use the updated version."
                )
            else:
                print("Update failed. Please check the logs or try manual installation.")
                sys.exit(1)
        except Exception as e:
            logger.error("Update failed with error: %s", e)
            print(f"Update failed: {e}")
            sys.exit(1)
