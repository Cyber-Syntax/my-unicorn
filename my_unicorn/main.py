#!/usr/bin/python3
"""Main module for my-unicorn CLI application.

This module configures logging, loads configuration files, and executes commands.
"""

import argparse
import gettext
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from my_unicorn.app_config import AppConfigManager
from my_unicorn.auth_manager import GitHubAuthManager
from my_unicorn.catalog import initialize_definitions_path
from my_unicorn.commands.customize_app_config import CustomizeAppConfigCommand
from my_unicorn.commands.customize_global_config import CustomizeGlobalConfigCommand
from my_unicorn.commands.delete_backups import DeleteBackupsCommand
from my_unicorn.commands.install_catalog import InstallAppCommand
from my_unicorn.commands.install_url import DownloadCommand
from my_unicorn.commands.invoker import CommandInvoker
from my_unicorn.commands.manage_token import ManageTokenCommand
from my_unicorn.commands.migrate_config import MigrateConfigCommand
from my_unicorn.commands.update_all_async import UpdateAsyncCommand
from my_unicorn.commands.update_all_auto import UpdateAllAutoCommand
from my_unicorn.commands.version import VersionCommand
from my_unicorn.global_config import GlobalConfigManager

_ = gettext.gettext

# Constants
LOW_API_REQUESTS_THRESHOLD = 100
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def custom_excepthook(
    exc_type: type[BaseException], exc_value: BaseException, exc_traceback: TracebackType | None
) -> None:
    """Custom excepthook to log uncaught exceptions.

    Args:
        exc_type: Type of the exception
        exc_value: Exception instance
        exc_traceback: Traceback object

    """
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def display_github_api_status() -> None:
    """Display GitHub API rate limit information to the user.

    Uses estimated values from cache to avoid API calls during startup.
    """
    try:
        # Use estimated method instead of get_rate_limit_info to avoid API calls during startup
        rate_info = GitHubAuthManager.get_estimated_rate_limit_info()
        if hasattr(rate_info, "__len__") and len(rate_info) >= 4:
            remaining, limit, reset_time, is_authenticated = rate_info[:4]
        else:
            remaining, limit = rate_info[:2]
            reset_time, is_authenticated = "unknown", False

        # Create a status display for API rate limit information
        print("\n--- GitHub API Status ---")

        if is_authenticated:
            # Convert remaining to int for comparison
            remaining_int = int(remaining) if remaining else 0
            print(f"GitHub API Status: {remaining} of {limit} requests remaining")
            print("Authentication: ✅ Authenticated")
            print(f"Reset Time: {reset_time}")

            if remaining_int < LOW_API_REQUESTS_THRESHOLD:
                print("Warning: ⚠️ Low API requests remaining!")
        else:
            print(f"GitHub API Status: {remaining} of 60 requests remaining")
            print("Authentication: ❌ Unauthenticated")
            print("Note: 🔑 Add token (option 7) for 5000 requests/hour")

        print(f"{'-' * 40}")
    except Exception as e:
        logging.debug(f"Error checking rate limits: {e}")


def display_menu() -> None:
    """Display the main application menu."""
    print(f"\n{'=' * 60}")
    print("                 Welcome to my-unicorn 🦄")
    print(f"{'=' * 60}")

    # Display GitHub API rate limit info if available
    display_github_api_status()

    # Download & Update section
    print("\n--- Download & Update ---")
    print("1. Download new AppImage from URL")
    print("2. Install app from catalog")
    print("3. Update all AppImages")
    print("4. Select AppImages to update")

    # Configuration section
    print("\n--- Configuration ---")
    print("5. Manage AppImage settings")
    print("6. Manage global settings")
    print("7. Manage GitHub token")

    # Maintenance section
    print("\n--- Maintenance ---")
    print("8. Update configuration files")
    print("9. Clean old backups")
    print("10. Show version")
    print("0. Exit")
    print(f"{'-' * 40}")


def get_user_choice() -> int:
    """Display menu and get user choice using standard terminal output.

    Returns:
        int: The user's menu choice as an integer

    Raises:
        ValueError: If user input cannot be converted to an integer
        KeyboardInterrupt: If user cancels with Ctrl+C

    """
    display_menu()

    try:
        choice = input("\nEnter your choice: ")
        return int(choice)
    except ValueError as error:
        print(f"Invalid input: {error}")
        logging.error(f"Invalid menu choice: {error}", exc_info=True)
        sys.exit(EXIT_FAILURE)
    except KeyboardInterrupt:
        logging.info("User interrupted the program with Ctrl+C")
        print("\nProgram interrupted. Exiting gracefully...")
        sys.exit(EXIT_SUCCESS)


def get_xdg_state_home() -> Path:
    """Get the XDG state home directory."""
    xdg_state_home = os.getenv("XDG_STATE_HOME")
    if not xdg_state_home or not Path(xdg_state_home).is_absolute():
        return Path.home() / ".local" / "state"
    return Path(xdg_state_home)


def configure_logging() -> None:
    """Configure logging for the application."""
    log_dir_base = get_xdg_state_home()

    log_dir = log_dir_base / "my-unicorn"
    log_dir.mkdir(parents=True, exist_ok=True)  # Use parents=True to create intermediate dirs
    log_file = "my-unicorn.log"
    log_file_path = log_dir / log_file

    # Configure file handler for all log levels
    file_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=3)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Configure console handler for ERROR and above only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)  # Only show errors and above in console
    console_formatter = logging.Formatter("%(message)s")  # Simpler format for console
    console_handler.setFormatter(console_formatter)

    # Get root logger and configure it
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Remove any existing handlers (in case this function is called multiple times)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add the configured handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info("Logging configured with DEBUG level")


def setup_commands(invoker: CommandInvoker) -> None:
    """Register all available commands with the command invoker.

    Args:
        invoker: The CommandInvoker instance to register commands with

    """
    invoker.register_command(1, DownloadCommand())
    invoker.register_command(2, InstallAppCommand())
    invoker.register_command(3, UpdateAllAutoCommand())
    invoker.register_command(4, UpdateAsyncCommand())
    invoker.register_command(5, CustomizeAppConfigCommand())
    invoker.register_command(6, CustomizeGlobalConfigCommand())
    invoker.register_command(7, ManageTokenCommand())
    invoker.register_command(8, MigrateConfigCommand())
    invoker.register_command(9, DeleteBackupsCommand())
    invoker.register_command(10, VersionCommand())


def initialize_app_definitions() -> None:
    """Initialize the path to application definition JSONs.

    This sets up the apps/ directory path relative to the application root.
    """
    app_root = Path(__file__).parent
    apps_dir = app_root / "apps"

    if not apps_dir.exists():
        logging.info("Creating apps directory for JSON definitions")
        apps_dir.mkdir(exist_ok=True)

    logging.info(f"Initializing app definitions path: {apps_dir}")
    initialize_definitions_path(apps_dir)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the main argument parser for CLI usage."""
    parser = argparse.ArgumentParser(
        description="my-unicorn: AppImage management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
%(prog)s # Interactive mode (default)
%(prog)s version # Show current version
%(prog)s version --check # Check for updates
%(prog)s version --update # Update to latest version
%(prog)s download https://github.com/johannesjo/super-productivity # Download AppImage from URL
%(prog)s install joplin # Install AppImage from catalog
%(prog)s update --all # Update all AppImages
%(prog)s update --select joplin,super-productivity # Select AppImages to update
%(prog)s token --save # Save GitHub token to keyring
%(prog)s token --remove # Remove GitHub token
%(prog)s token --check # Check GitHub API rate limits
%(prog)s migrate --clean # Migrate configuration files
%(prog)s migrate --force # Migrate configuration without confirmation
""",
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Version command
    version_parser = subparsers.add_parser("version", help="Display version and manage updates")
    version_cmd = VersionCommand()
    version_cmd.add_arguments(version_parser)

    # Download command
    download_parser = subparsers.add_parser("download", help="Download AppImage from URL")
    download_parser.add_argument("url", help="GitHub repository URL")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install app from catalog")
    install_parser.add_argument("app_name", nargs="?", help="Application name to install")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update AppImages")
    update_group = update_parser.add_mutually_exclusive_group()
    update_group.add_argument("--all", action="store_true", help="Update all apps")
    update_group.add_argument("--select", action="store_true", help="Select apps to update")

    # Token command
    token_parser = subparsers.add_parser("token", help="GitHub token management")
    token_parser.add_argument("--save", action="store_true", help="Save token to keyring")
    token_parser.add_argument("--remove", action="store_true", help="Remove token")
    token_parser.add_argument("--check", action="store_true", help="Check rate limits")

    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate configuration files")
    migrate_parser.add_argument("--clean", action="store_true", help="Remove unused settings")
    migrate_parser.add_argument("--force", action="store_true", help="Remove without confirmation")

    return parser


def execute_cli_command(args: argparse.Namespace) -> None:
    """Execute a CLI command based on parsed arguments."""
    invoker = CommandInvoker()
    setup_commands(invoker)

    if args.command == "version":
        cmd = VersionCommand()
        cmd.set_args(args)
        cmd.execute()
        return

    if args.command == "download":
        # Set URL and execute download command
        cmd = DownloadCommand()
        # You'd need to modify DownloadCommand to accept URL parameter
        cmd.execute()

    elif args.command == "install":
        cmd = InstallAppCommand()
        # You'd need to modify InstallAppCommand to accept app_name parameter
        cmd.execute()

    elif args.command == "update":
        if args.all:
            invoker.execute_command(3)  # UpdateAllAutoCommand
        elif args.select:
            invoker.execute_command(4)  # UpdateAsyncCommand
        else:
            print("Please specify --all or --select for update command")

    elif args.command == "config":
        if args.config_type == "app":
            invoker.execute_command(5)  # CustomizeAppConfigCommand
        elif args.config_type == "global":
            invoker.execute_command(6)  # CustomizeGlobalConfigCommand
        else:
            print("Please specify 'app' or 'global' for config command")

    elif args.command == "token":
        cmd = ManageTokenCommand()
        # You'd need to modify ManageTokenCommand to handle CLI flags
        cmd.execute()

    elif args.command == "migrate":
        cmd = MigrateConfigCommand()
        cli_args = []
        if args.clean:
            cli_args.append("--clean")
        if args.force:
            cli_args.append("--force")
        cmd.execute(cli_args)

    elif args.command == "cleanup":
        invoker.execute_command(9)  # DeleteBackupsCommand


def main() -> None:
    """Main function to initialize and run the application."""
    configure_logging()

    # Parse command line arguments
    parser = create_argument_parser()
    args = parser.parse_args()

    # Initialize app definitions path
    initialize_app_definitions()

    # Config Initialize, global config auto loads the config file
    # Commands create the config file if it doesn't exist
    global_config = GlobalConfigManager()
    app_config = AppConfigManager()

    # TODO: Uncomment and implement locale management
    # Initialize LocaleManager and set locale
    # locale_manager = LocaleManager()
    # locale_manager.load_translations(global_config.locale)

    if args.command:
        # If command line arguments are provided, execute the CLI command
        execute_cli_command(args)
    else:
        # Initialize CommandInvoker and register commands
        invoker = CommandInvoker()
        setup_commands(invoker)

        # Main menu loop
        while True:
            choice = get_user_choice()
            if choice == 0:
                logging.info("User selected to exit application")
                print("Exiting...")
                sys.exit(EXIT_SUCCESS)
            invoker.execute_command(choice)


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
