#!/usr/bin/python3
import os
import sys
import logging
import json
from src.file_handler import FileHandler
import gettext
from babel.support import Translations
from logging.handlers import RotatingFileHandler
from src.locale import LocaleManager


_ = gettext.gettext
file_handler = FileHandler
locale_manager = LocaleManager


def custom_excepthook(exc_type, exc_value, exc_traceback):
    """Custom excepthook to log uncaught exceptions"""
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def get_user_choice():
    """Display menu and get user choice"""
    print(_("Welcome to the my-unicorn 🦄!"))
    print(_("Choose one of the following options:"))
    print("====================================")
    print(_("1. Update AppImage by config file"))
    print(_("2. Download new AppImage (create config file)"))
    print(_("3. Customize AppImage config file"))
    print(_("4. Update all AppImages"))
    print(_("5. Change Language"))
    print(_("6. Exit"))
    print("====================================")
    try:
        return int(input(_("Enter your choice: ")))
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print(_("Error: {error}. Exiting...").format(error=error))
        sys.exit(1)


def main():


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
