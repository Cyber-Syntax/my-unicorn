#!/usr/bin/python3
import sys
import logging
from src.file_handler import FileHandler
from babel.support import Translations
import gettext


def custom_excepthook(exc_type, exc_value, exc_traceback):
    """Custom excepthook to log uncaught exceptions"""
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def configure_logging():
    """Set up the logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
        filename="logs/my-unicorn.log",
    )


def select_language(self):
    """Display language options and set the selected language"""
    global _
    languages = {1: "en", 2: "tr"}
    current_locale = self.get_locale_config()
    if current_locale:
        translations = Translations.load(self.file_path, [current_locale])
        translations.install()
        _ = translations.gettext
        return

    print("Choose your language / Dilinizi seçin:")
    print("1. English")
    print("2. Türkçe")

    try:
        choice = int(input("Enter your choice: "))
        if choice in languages:
            language = languages[choice]
            self.save_locale_config(language)
            translations = Translations.load(self.file_path, [language])
            translations.install()
            _ = translations.gettext
        else:
            print("Invalid choice. Defaulting to English.")
            _ = gettext.gettext
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print("Invalid input. Defaulting to English.")
        _ = gettext.gettext


def get_user_choice():
    """Display menu and get user choice"""
    print(_("Welcome to the my-unicorn 🦄!"))
    print(_("Choose one of the following options:"))
    print("====================================")
    print(_("1. Update AppImage by config file"))
    print(_("2. Download new AppImage (create config file)"))
    print(_("3. Customize AppImage config file"))
    print(_("4. Update all AppImages"))
    print(_("5. Exit"))
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
    1. Select language.
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
    file_handler = FileHandler()
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
