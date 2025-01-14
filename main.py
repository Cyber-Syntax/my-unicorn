#!/usr/bin/python3
import os
import sys
import logging
import json
from src.file_handler import FileHandler
import gettext
from babel.support import Translations
from logging.handlers import RotatingFileHandler

_ = gettext.gettext
file_handler = FileHandler()


def get_locale_config(file_path):
    """Load the locale configuration from the config file."""
    if os.path.exists(file_handler.config_path):
        with open(file_handler.config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
            return config.get("locale")  # Return None if no locale is set
    return None  # Return None if no config file exists


def save_locale_config(file_path, locale):
    """Save the selected locale to the config file."""
    print(f"Saving locale config to {file_handler.config_path}")  # Debug statement
    os.makedirs(os.path.dirname(file_handler.config_path), exist_ok=True)
    with open(file_handler.config_path, "w", encoding="utf-8") as file:
        json.dump({"locale": locale}, file, indent=4)
    print(f"Locale saved as: {locale}")  # Debug statement


def load_translations(locale):
    """Load translations for the specified locale."""
    locales_dir = os.path.join(os.path.dirname(__file__), "locales")
    translations = Translations.load(locales_dir, [locale])
    translations.install()
    global _
    _ = translations.gettext


def select_language(file_path):
    """Display language options and set the selected language"""
    global _
    languages = {1: "en", 2: "tr"}
    current_locale = get_locale_config(file_path)
    if current_locale:
        load_translations(current_locale)
        return

    print("Choose your language / Dilinizi seçin:")
    print("1. English")
    print("2. Türkçe")

    try:
        choice = int(input("Enter your choice: "))
        if choice in languages:
            language = languages[choice]
            save_locale_config(file_path, language)
            load_translations(language)
        else:
            print("Invalid choice. Defaulting to English.")
            _ = gettext.gettext
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print("Invalid input. Defaulting to English.")
        _ = gettext.gettext


def update_locale(file_handler):
    """Update the locale.json file with the selected language."""
    languages = {1: "en", 2: "tr"}
    print("Choose your language / Dilinizi seçin:")
    for key, value in languages.items():
        print(f"{key}. {value}")

    try:
        choice = int(input("Enter your choice: "))
        if choice in languages:
            language = languages[choice]
            print(
                f"Updating locale config to {file_handler.config_path}"
            )  # Debug statement
            os.makedirs(os.path.dirname(file_handler.config_path), exist_ok=True)
            with open(file_handler.config_path, "w", encoding="utf-8") as file:
                json.dump({"locale": language}, file, indent=4)
            print(f"Locale updated to: {language}")  # Debug statement
        else:
            print("Invalid choice.")
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print("Invalid input.")


def custom_excepthook(exc_type, exc_value, exc_traceback):
    """Custom excepthook to log uncaught exceptions"""
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def configure_logging():
    """Set up the logging configuration"""
    log_file_path = os.path.join(os.path.dirname(__file__), "logs/my-unicorn.log")
    log_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=1024 * 1024,
        backupCount=3,  # 1MB per file, keep 3 backups
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    log_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(
        logging.INFO
    )  # Logs INFO and above (INFO, WARNING, ERROR, CRITICAL)
    logger.addHandler(log_handler)


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


def run_functions(file_handler, function_list):
    """Run the provided list of functions on the file handler"""
    for function in function_list:
        if hasattr(file_handler, function):
            getattr(file_handler, function)()
        else:
            print(_("Function {function} not found").format(function=function))
            logging.error(
                _("Function {function} not found").format(function=function),
                exc_info=True,
            )
            sys.exit()


def choice_update(file_handler, functions):
    """Handle choice 1: Update existing AppImage"""
    file_handler.list_json_files()
    if file_handler.choice in [3, 4]:
        run_functions(file_handler, functions[file_handler.choice])


def choice_download(file_handler, functions):
    """Handle choice 2: Download new AppImage"""
    print(_("Downloading new appimage"))
    print(_("Choose one of the following options: \n"))
    print("====================================")
    print(_("1. Backup old appimage and download new appimage"))
    print(_("2. Download new appimage and overwrite old appimage"))
    file_handler.choice = int(input(_("Enter your choice: ")))
    run_functions(file_handler, functions[file_handler.choice])


def main():
    """
    Main function workflow:
    1. Select language if not configured.
    2. List all JSON files using list_json_files().
    3. Select a JSON file (e.g., joplin.json).
    4. Load credentials from the selected JSON file via load_credentials().
    5. Get a response from the GitHub API using get_response().
    6. Download the AppImage using download().
    7. Use save_credentials function to save owner, repo, hash_type, choice...
    8. Verify file integrity with hash file and appimage
    9. Make executable, delete version from appimage_name and move to directory
    """
    configure_logging()

    if not os.path.isfile(file_handler.config_path):
        select_language(file_handler.file_path)
    else:
        current_locale = get_locale_config(file_handler.file_path)
        if current_locale:
            load_translations(current_locale)
    choice = get_user_choice()

    functions = {
        1: [
            "ask_inputs",
            "learn_owner_repo",
            "get_response",
            "download",
            "save_credentials",
            "verify_sha",
            "make_executable",
            "handle_file_operations",
        ],
        2: [
            "ask_inputs",
            "learn_owner_repo",
            "get_response",
            "download",
            "save_credentials",
            "verify_sha",
            "make_executable",
            "handle_file_operations",
        ],
        3: [
            "get_response",
            "download",
            "verify_sha",
            "make_executable",
            "handle_file_operations",
        ],
        4: [
            "get_response",
            "download",
            "verify_sha",
            "make_executable",
            "handle_file_operations",
        ],
    }

    try:
        if choice == 1:
            choice_update(file_handler, functions)
        elif choice == 2:
            choice_download(file_handler, functions)
        elif choice == 3:
            file_handler.list_json_files()
            file_handler.update_json()
        elif choice == 4:
            file_handler.check_updates_json_all()
        elif choice == 5:
            update_locale(file_handler)
        elif choice == 6:
            print(_("Exiting..."))
            sys.exit()
        else:
            print(_("Invalid choice"))
            sys.exit()
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print(_("Error: {error}. Exiting...").format(error=error))
        sys.exit(1)


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
