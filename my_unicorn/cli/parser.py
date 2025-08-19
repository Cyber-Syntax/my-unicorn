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
  # Install from catalog (comma-separated)
  %(prog)s install appflowy,joplin,obsidian

  # Install from GitHub repository URL
  %(prog)s install https://github.com/pbek/QOwnNotes

  # Update appimages
  %(prog)s update appflowy,joplin
  %(prog)s update appflowy joplin
  %(prog)s update

  # my-unicorn update and check
  %(prog)s self-update --check-only
  %(prog)s self-update

  # Other commands
  %(prog)s list                # Show installed appimages
  %(prog)s list --available    # Available appimages via catalog installation

  # Auth Token Management
  %(prog)s auth --save-token
  %(prog)s auth --remove-token
  %(prog)s auth --status
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
        self._add_self_update_command(subparsers)
        self._add_list_command(subparsers)
        self._add_remove_command(subparsers)
        self._add_backup_command(subparsers)
        self._add_auth_command(subparsers)
        self._add_config_command(subparsers)

    def _add_install_command(self, subparsers) -> None:
        """Add install command parser.

        Args:
            subparsers: The subparsers object to add the install command to

        """
        install_parser = subparsers.add_parser(
            "install",
            help="Install AppImages from catalog or URLs",
            epilog="""
Examples:
  # Install single app from catalog
  %(prog)s obsidian

  # Install multiple apps (comma-separated)
  %(prog)s appflowy,joplin,obsidian

  # Install from GitHub repository URL
  %(prog)s https://github.com/pbek/QOwnNotes
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        install_parser.add_argument(
            "targets",
            nargs="+",
            help="Catalog app names or GitHub repository URLs (comma-separated)",
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
  %(prog)s                    # Update all installed apps
  %(prog)s appflowy joplin    # Update specific apps (without comma)
  %(prog)s appflowy,joplin    # Update specific apps (with comma)
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        update_parser.add_argument(
            "apps",
            nargs="*",
            help="App names to update (comma-separated supported, empty to update all)",
        )
        update_parser.add_argument(
            "--check-only",
            action="store_true",
            help="Only check for updates without installing",
        )
        update_parser.add_argument(
            "--verbose", action="store_true", help="Show detailed logging during update"
        )

    def _add_self_update_command(self, subparsers) -> None:
        """Add self-update command parser.

        Args:
            subparsers: The subparsers object to add the self-update command to

        """
        self_update_parser = subparsers.add_parser(
            "self-update",
            help="Update my-unicorn itself from GitHub",
            epilog="""
Examples:
  %(prog)s --check-only    # Check for updates only
  %(prog)s                 # Update if available
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self_update_parser.add_argument(
            "--check-only",
            action="store_true",
            help="Only check for updates without installing",
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
        remove_parser = subparsers.add_parser(
            "remove",
            help="Remove installed AppImages",
            epilog="""
    Examples:
        %(prog)s appflowy
        %(prog)s appflowy --keep-config
    """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        (remove_parser.add_argument("apps", nargs="+", help="Application names to remove"),)
        remove_parser.add_argument(
            "--keep-config", action="store_true", help="Keep configuration files"
        )

    def _add_backup_command(self, subparsers) -> None:
        """Add backup command parser.

        Args:
            subparsers: The subparsers object to add the backup command to

        """
        backup_parser = subparsers.add_parser(
            "backup",
            help="Manage AppImage backups and restore",
            epilog="""
Examples:
  # Create backup
  %(prog)s appflowy

  # Restore latest backup
  %(prog)s appflowy --restore-last

  # Restore specific version
  %(prog)s appflowy --restore-version 1.2.3

  # List backups for specific app
  %(prog)s appflowy --list-backups



  # Show backup info
  %(prog)s appflowy --info

  # Cleanup old backups
  %(prog)s --cleanup
  %(prog)s appflowy --cleanup

  # Migrate old backup format
  %(prog)s --migrate
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        backup_parser.add_argument(
            "app_name", nargs="?", help="Application name (required for most operations)"
        )

        # Action group - mutually exclusive options
        action_group = backup_parser.add_mutually_exclusive_group()

        action_group.add_argument(
            "--restore-last", action="store_true", help="Restore the latest backup version"
        )

        action_group.add_argument(
            "--restore-version", type=str, metavar="VERSION", help="Restore a specific version"
        )

        action_group.add_argument(
            "--list-backups",
            action="store_true",
            help="List available backups for the specified app",
        )

        action_group.add_argument(
            "--cleanup",
            action="store_true",
            help="Clean up old backups according to max_backup setting",
        )

        action_group.add_argument(
            "--info", action="store_true", help="Show detailed backup information"
        )

        action_group.add_argument(
            "--migrate",
            action="store_true",
            help="Migrate old backup files to new folder-based format",
        )

    def _add_auth_command(self, subparsers) -> None:
        """Add auth command parser.

        Args:
            subparsers: The subparsers object to add the auth command to

        """
        auth_parser = subparsers.add_parser("auth", help="Manage GitHub authentication")
        auth_group = auth_parser.add_mutually_exclusive_group(required=True)
        auth_group.add_argument(
            "--save-token", action="store_true", help="Save GitHub authentication token"
        )
        auth_group.add_argument(
            "--remove-token", action="store_true", help="Remove GitHub authentication token"
        )
        auth_group.add_argument(
            "--status", action="store_true", help="Show authentication status"
        )

    def _add_config_command(self, subparsers) -> None:
        """Add config command parser.

        Args:
            subparsers: The subparsers object to add the config command to

        """
        config_parser = subparsers.add_parser("config", help="Manage configuration")
        config_group = config_parser.add_mutually_exclusive_group(required=True)
        config_group.add_argument(
            "--show", action="store_true", help="Show current configuration"
        )
        config_group.add_argument(
            "--reset", action="store_true", help="Reset configuration to defaults"
        )
