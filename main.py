#!/usr/bin/python3
import sys
import logging
from cls.FileHandler import FileHandler

def custom_excepthook(exc_type, exc_value, exc_traceback):
    """Custom excepthook to log uncaught exceptions"""
    # Log the exception
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    # Call the original excepthook to ensure Python's default error handling
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def main():
    """
        ## How method works:
        1. Call list_json_files() method to list all json files.
        2. We selecting .json file (e.g joplin.json)
        3. We loading credentials from joplin.json file via load_credentials() method.
        4. We geting response from github api via get_response() method.
        5. We downloading appimage via download() method.
        6. Other stuff just file handling.
    """

    # Set up the logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
        filename="logs/my-unicorn.log",
    )
    # Create a FileHandler with write mode
    file_handler = logging.FileHandler("logs/my-unicorn.log", "w")
    # Create an instance of the FileHandler class
    file_handler = FileHandler()

    # A dictionary of functions to call based on the user's choice
    """
    @param choice: The user's choice to update the appimage or download a new appimage
    @type choice: int
    @param choice 1: Download new appimage and backup old appimage
    @param choice 2: Download new appimage and overwrite old appimage
    @param choice 3: Update json file and backup old appimage
    @param choice 4: Update json file and overwrite old appimage
    """

    functions = {
        1: ['ask_inputs',
            'learn_owner_repo',
            'get_response',
            'download',
            'save_credentials',
            'verify_sha',
            'make_executable',
            'handle_file_operations',
            ],

        2: ['ask_inputs',
            'learn_owner_repo',
            'get_response',
            'download',
            'save_credentials',
            'verify_sha',
            'make_executable',
            'handle_file_operations',
            ],

        3: ['get_response',
            'download',
            'verify_sha',
            'make_executable',
            'handle_file_operations',
            ],

        4: ['get_response',
            'download',
            'verify_sha',
            'make_executable',
            'handle_file_operations',
            ]
    }

    print("Welcome to the my-unicorn 🦄!")
    print("Choose one of the following options:")
    print("====================================")
    print("1. Update existing AppImage")
    print("2. Download new AppImage")
    print("3. Update AppImage config(.json) file")
    print("4. Check updates for all AppImages and update all")
    print("5. Exit")
    print("====================================")
    try:
        choice = int(input("Enter your choice: "))
    except (ValueError, KeyboardInterrupt) as error:
        logging.error(f"Error: {error}", exc_info=True)
        print(f"Error: {error}. Exiting...")
        sys.exit(1)
    else:
        try:
            # Call the methods based on the user's choice
            if choice == 1:
                file_handler.list_json_files()
                if file_handler.choice in [3, 4]:
                    for function in functions[file_handler.choice]:
                        if function in dir(file_handler):
                            method = getattr(file_handler, function)
                            method()
                        else:
                            print(f"Function {function} not found")
            elif choice == 2:
                print("Downloading new appimage")
                print("Choose one of the following options: \n")
                print("====================================")
                print("1. Backup old appimage and download new appimage")
                print("2. Download new appimage and overwrite old appimage")
                file_handler.choice = int(input("Enter your choice: "))
                for function in functions[file_handler.choice]:
                    if function in dir(file_handler):
                        method = getattr(file_handler, function)
                        method()
                    else:
                        print(f"Function {function} not found")
                        logging.error(f"Function {function} not found", exc_info=True)
                        sys.exit()
            elif choice == 3:
                # choose the json file first
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
