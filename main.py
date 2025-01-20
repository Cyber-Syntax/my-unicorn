#!/usr/bin/python3
import os
import sys
import logging
import gettext
from logging.handlers import RotatingFileHandler
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.locale import LocaleManager
from src.update import AppImageUpdater

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
    print(_("1. Create AppImage Config File (Must be created to install/update)"))
    print(_("2. Update all AppImages"))
    print(_("3. Customize global config file"))
    print(_("4. Customize AppImage config file"))
    print(_("5. Exit"))
    print("====================================")
    try:
        return int(input(_("Enter your choice: ")))
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print(_("Error: {error}. Exiting...").format(error=error))
        sys.exit(1)


def configure_logging():
    """Configure logging for the application."""
    log_file_path = os.path.join(os.path.dirname(__file__), "logs/my-unicorn.log")
    log_handler = RotatingFileHandler(
        log_file_path, maxBytes=1024 * 1024, backupCount=3
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    log_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)


def main():
    # Configure logging
    configure_logging()

    # Setup Global Configuration if user doesn't have one
    app_config = AppConfigManager()
    global_config = GlobalConfigManager()
    global_config.load_config()

    # # Instantiate LocaleManager and set locale
    # locale_manager = LocaleManager()
    # locale_manager.load_translations(global_config.locale)

    # Get user choice
    choice = get_user_choice()

    # Handle user choices
    if choice == 1:
        app_config.create_app_config()

    elif choice == 2:
        # Initialize updater with appropriate managers
        updater = AppImageUpdater(global_config)
        updater.update_all()

    elif choice == 3:
        logging.info(_("Customizing global configuration..."))
        global_config.customize_global_config(global_config)

    elif choice == 4:
        logging.info(_("Customizing AppImage configuration..."))
        app_config.customize_app_config()

    elif choice == 5:
        print(_("Exiting..."))
        sys.exit()

    else:
        print(_("Invalid choice. Please try again."))


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
