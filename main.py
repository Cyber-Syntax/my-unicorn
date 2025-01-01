#!/usr/bin/python3
import sys
import logging
from src.file_handler import FileHandler


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


def get_user_choice():
    """Display menu and get user choice"""
    print("Welcome to the my-unicorn 🦄!")
    print("Choose one of the following options:")
    print("====================================")
    print("1. Update existing AppImage")
    print("2. Download new AppImage")
    print("3. Update/Customize AppImage config(.json) file")
    print("4. Check updates for all AppImages and update all")
    print("5. Exit")
    print("====================================")
    try:
        return int(input("Enter your choice: "))
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print(f"Error: {error}. Exiting...")
        sys.exit(1)


def run_functions(file_handler, function_list):
    """Run the provided list of functions on the file handler"""
    for function in function_list:
        if hasattr(file_handler, function):
            getattr(file_handler, function)()
        else:
            print(f"Function {function} not found")
            logging.error(f"Function {function} not found", exc_info=True)
            sys.exit()


def choice_update(file_handler, functions):
    """Handle choice 1: Update existing AppImage"""
    file_handler.list_json_files()
    if file_handler.choice in [3, 4]:
        run_functions(file_handler, functions[file_handler.choice])


def choice_download(file_handler, functions):
    """Handle choice 2: Download new AppImage"""
    print("Downloading new appimage")
    print("Choose one of the following options: \n")
    print("====================================")
    print("1. Backup old appimage and download new appimage")
    print("2. Download new appimage and overwrite old appimage")
    file_handler.choice = int(input("Enter your choice: "))
    run_functions(file_handler, functions[file_handler.choice])


def main():
    """
    Main function workflow:
    1. List all JSON files using list_json_files().
    2. Select a JSON file (e.g., joplin.json).
    3. Load credentials from the selected JSON file via load_credentials().
    4. Get a response from the GitHub API using get_response().
    5. Download the AppImage using download().
    6. Use save_credentials function to save owner, repo, hash_type, choice...
    7. Verify file integrity with hash file and appimage
    8. Make executable, delete version from appimage_name and move to directory
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
            print("Exiting...")
            sys.exit()
        else:
            print("Invalid choice")
            sys.exit()
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print(f"Error: {error}. Exiting...")
        sys.exit(1)


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
