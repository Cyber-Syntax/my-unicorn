#!/usr/bin/python3
import gettext
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from commands.create_app_config import CreateAppConfigCommand
from commands.customize_app_config import CustomizeAppConfigCommand
from commands.customize_global_config import CustomizeGlobalConfigCommand
from commands.download import DownloadCommand
from commands.invoker import CommandInvoker
from commands.update_all import UpdateCommand
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.locale import LocaleManager

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
    print(_("2. Update all AppImages"))
    print(_("3. Customize AppImages config file"))
    print(_("4. Customize Global config file"))
    print(_("5. Exit"))
    print(_("6. Help"))
    print("====================================")
    try:
        return int(input(_("Enter your choice: ")))
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print(_("Error: {error}. Exiting...").format(error=error))
        sys.exit(1)


def configure_logging():
    """Configure logging for the application."""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = "my-unicorn.log"
    log_file_path = os.path.join(log_dir, log_file)

    log_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=3)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    log_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)


def display_help():
    """Display help information for each command"""
    help_text = """
    Welcome to my-unicorn 🦄!
    This script helps you manage AppImages using the command design pattern.

    Available commands:
    1. Download AppImage: Download a new AppImage and create a config file.
    2. Update all AppImages: Update all existing AppImages based on their config files.
    3. Customize AppImages config file: Customize the configuration file for a specific AppImage.
    4. Customize Global config file: Customize the global configuration settings.
    5. Exit: Exit the script.
    6. Help: Display this help information.

    For more information, refer to the documentation or contact support.
    """
    print(help_text)


def main():
    configure_logging()

    global_config = GlobalConfigManager()
    app_config = AppConfigManager()

    invoker = CommandInvoker()

    invoker.register_command(1, DownloadCommand())
    invoker.register_command(2, UpdateCommand())
    invoker.register_command(3, CustomizeAppConfigCommand())
    invoker.register_command(4, CustomizeGlobalConfigCommand())

    while True:
        choice = get_user_choice()
        if choice == 5:
            print("Exiting...")
            sys.exit(0)
        elif choice == 6:
            display_help()
        else:
            try:
                invoker.execute_command(choice)
            except Exception as e:
                logging.error(f"Error executing command: {e}", exc_info=True)
                print(_("An error occurred while executing the command. Please try again."))


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
