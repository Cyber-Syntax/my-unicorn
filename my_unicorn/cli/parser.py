"""CLI argument parser for my-unicorn.

This module handles the parsing of command-line arguments and provides
a clean interface for defining CLI commands and their options.
"""

import argparse
from argparse import Namespace
from typing import Any


class CLIParser:
    """Command-line argument parser for my-unicorn."""

    def __init__(self, global_config: dict[str, Any]) -> None:
        """Initialize the CLI parser with global configuration.

        Args:
            global_config: Global configuration dictionary

        """
        self.global_config = global_config

    def parse_args(self) -> Namespace:
        """Parse command-line arguments.

        Returns:
            Parsed arguments namespace

        """
        parser = self._create_main_parser()
        self._add_subcommands(parser)
        return parser.parse_args()

    def _create_main_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser.

        Returns:
            The configured main ArgumentParser instance

        """
        return argparse.ArgumentParser(
            description="my-unicorn AppImage Installer",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Install from GitHub URL
  %(prog)s install https://github.com/AppFlowy-IO/AppFlowy

  # Install from catalog (comma-separated)
  %(prog)s install appflowy,joplin,obsidian

  # Update apps
  %(prog)s update appflowy,joplin
  %(prog)s update

  # Other commands
  %(prog)s list
  %(prog)s auth --save-token
            """,
        )

    def _add_subcommands(self, parser: argparse.ArgumentParser) -> None:
        """Add all subcommands to the parser.

        Args:
            parser: The main ArgumentParser instance to add subcommands to

        """
        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        self._add_install_command(subparsers)
        self._add_update_command(subparsers)
        self._add_list_command(subparsers)
        self._add_remove_command(subparsers)
        self._add_auth_command(subparsers)
        self._add_config_command(subparsers)

    def _add_install_command(self, subparsers) -> None:
        """Add install command parser.

        Args:
            subparsers: The subparsers object to add the install command to

        """
        install_parser = subparsers.add_parser(
            "install",
            help="Install AppImages from URLs or catalog",
            epilog="""
Examples:
  # Install from GitHub URL
  %(prog)s install https://github.com/AppFlowy-IO/AppFlowy

  # Install from catalog (comma-separated)
  %(prog)s install appflowy,joplin,obsidian

Note: Cannot mix URLs and catalog names in the same command
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        install_parser.add_argument(
            "targets",
            nargs="+",
            "GitHub URLs OR catalog app names (comma-separated, cannot mix types)",
        )
        install_parser.add_argument(
            "--concurrency",
            type=int,
            default=self.global_config["max_concurrent_downloads"],
            help="Maximum number of parallel installs",
        )
        install_parser.add_argument(
            "--no-icon", action="store_true", help="Skip downloading application icons"
        )
        install_parser.add_argument(
            "--no-verify", action="store_true", help="Skip AppImage verification"
        )
        install_parser.add_argument(
            "--no-desktop",
            action="store_true",
            help="Skip desktop entry creation (only affects install, not updates)",
        )
        install_parser.add_argument(
            "--verbose", action="store_true", help="Show detailed logging during installation"
        )

    def _add_update_command(self, subparsers) -> None:
        """Add update command parser.

        Args:
            subparsers: The subparsers object to add the update command to

        """
        update_parser = subparsers.add_parser(
            "update",
            help="Update installed AppImages",
            epilog="""
Examples:
  %(prog)s update                    # Update all installed apps
  %(prog)s update appflowy joplin    # Update specific apps
  %(prog)s update appflowy,joplin    # Comma-separated apps
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        update_parser.add_argument(
            "apps",
            nargs="*",
            help="App names to update (comma-separated supported, empty to update all)",
        )
        update_parser.add_argument(
            "--check-only", action="store_true", help="Only check for updates without installing"
        )
        update_parser.add_argument(
            "--verbose", action="store_true", help="Show detailed logging during update"
        )

    def _add_list_command(self, subparsers) -> None:
        """Add list command parser.

        Args:
            subparsers: The subparsers object to add the list command to

        """
        list_parser = subparsers.add_parser("list", help="List installed AppImages")
        list_parser.add_argument(
            "--available", action="store_true", help="Show available applications from catalog"
        )

    def _add_remove_command(self, subparsers) -> None:
        """Add remove command parser.

        Args:
            subparsers: The subparsers object to add the remove command to

        """
        remove_parser = subparsers.add_parser("remove", help="Remove installed AppImages")
        remove_parser.add_argument("apps", nargs="+", help="Application names to remove")
        remove_parser.add_argument(
            "--keep-config", action="store_true", help="Keep configuration files"
        )

    def _add_auth_command(self, subparsers) -> None:
        """Add auth command parser.

        Args:
            subparsers: The subparsers object to add the auth command to

        """
        auth_parser = subparsers.add_parser("auth", help="Manage GitHub authentication")
        auth_group = auth_parser.add_mutually_exclusive_group(required=True)
        auth_group.add_argument("--save-token", action="store_true", help="Save GitHub authentication token")
        auth_group.add_argument(
            "--remove-token", action="store_true", help="Remove GitHub authentication token"
        )
        auth_group.add_argument("--status", action="store_true", help="Show authentication status")

    def _add_config_command(self, subparsers) -> None:
        """Add config command parser.

        Args:
            subparsers: The subparsers object to add the config command to

        """
        config_parser = subparsers.add_parser("config", help="Manage configuration")
        config_group = config_parser.add_mutually_exclusive_group(required=True)
        config_group.add_argument("--show", action="store_true", help="Show current configuration")
        config_group.add_argument("--reset", action="store_true", help="Reset configuration to defaults")
