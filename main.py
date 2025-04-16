#!/usr/bin/python3
import gettext
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from commands.customize_app_config import CustomizeAppConfigCommand
from commands.customize_global_config import CustomizeGlobalConfigCommand
from commands.download import DownloadCommand
from commands.invoker import CommandInvoker
from commands.manage_token import ManageTokenCommand
from commands.update_all import UpdateCommand
from commands.update_all_auto import UpdateAllAutoCommand
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager

_ = gettext.gettext


def custom_excepthook(exc_type, exc_value, exc_traceback):
    """Custom excepthook to log uncaught exceptions"""
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def get_user_choice():
    """Display menu and get user choice"""
    print(_("Welcome to my-unicorn 🦄!"))
    print(_("Choose one of the following options:"))
    print("====================================")
    print(_("1. Download AppImage (Must be installed to create config file)"))
    print(_("2. Update selected AppImages"))
    print(_("3. Update all AppImages automatically"))
    print(_("4. Customize AppImages config file"))
    print(_("5. Customize Global config file"))
    print(_("6. Manage GitHub Token (for API rate limits)"))
    print(_("7. Exit"))
    print("====================================")
    try:
        return int(input(_("Enter your choice: ")))
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        logging.error("Error: {error}. Exiting...".format(error=error))
        print(_("Error: {error}. Exiting...").format(error=error))
        sys.exit(1)


def configure_logging():
    """Configure logging for the application."""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = "my-unicorn.log"
    log_file_path = os.path.join(log_dir, log_file)

    # Configure file handler for all log levels
    file_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=3)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)

    # Configure console handler for ERROR and above only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)  # Only show errors and above in console
    console_formatter = logging.Formatter("%(message)s")  # Simpler format for console
    console_handler.setFormatter(console_formatter)

    # Get root logger and configure it
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Base level for the logger

    # Remove any existing handlers (in case this function is called multiple times)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add the configured handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info("Logging configured successfully")


def main():
    configure_logging()

    # Config Initialize, global config auto loads the config file
    # Commands create the config file if it doesn't exist
    global_config = GlobalConfigManager()
    app_config = AppConfigManager()

    # # Instantiate LocaleManager and set locale
    # locale_manager = LocaleManager()
    # locale_manager.load_translations(global_config.locale)

    # Initialize CommandInvoker and register commands
    invoker = CommandInvoker()

    invoker.register_command(1, DownloadCommand())
    invoker.register_command(2, UpdateCommand())
    invoker.register_command(3, UpdateAllAutoCommand())
    invoker.register_command(4, CustomizeAppConfigCommand())
    invoker.register_command(5, CustomizeGlobalConfigCommand())
    invoker.register_command(6, ManageTokenCommand())

    # Main menu loop
    while True:
        choice = get_user_choice()
        if choice == 7:
            logging.info("User selected to exit application")
            print("Exiting...")
            sys.exit(0)
        invoker.execute_command(choice)


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
