#!/usr/bin/python3
"""Main module for my-unicorn CLI application.

This module configures logging, loads configuration files, and executes commands.
"""

# Standard library imports
import gettext
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Optional, Union

from src.app_catalog import initialize_definitions_path
from src.app_config import AppConfigManager
from src.auth_manager import GitHubAuthManager

# Local imports
from src.commands.customize_app_config import CustomizeAppConfigCommand
from src.commands.customize_global_config import CustomizeGlobalConfigCommand
from src.commands.delete_backups import DeleteBackupsCommand
from src.commands.download import DownloadCommand
from src.commands.install_app import InstallAppCommand
from src.commands.invoker import CommandInvoker
from src.commands.manage_token import ManageTokenCommand
from src.commands.migrate_config import MigrateConfigCommand
from src.commands.update_all_async import UpdateAsyncCommand
from src.commands.update_all_auto import UpdateAllAutoCommand
from src.global_config import GlobalConfigManager

_ = gettext.gettext

# Constants
LOW_API_REQUESTS_THRESHOLD = 100
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def custom_excepthook(
    exc_type: type[BaseException], exc_value: BaseException, exc_traceback: Optional[TracebackType]
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
        remaining, limit, reset_time, is_authenticated = (
            GitHubAuthManager.get_estimated_rate_limit_info()
        )

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


def configure_logging() -> None:
    """Configure logging for the application."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
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


def main() -> None:
    """Main function to initialize and run the application."""
    configure_logging()

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
