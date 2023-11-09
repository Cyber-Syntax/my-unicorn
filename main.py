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
    functions = {
        1: ['ask_inputs',
            'learn_owner_repo', 
            'get_response', 
            'download',
            'save_credentials', 
            'backup_old_appimage', 
            'verify_sha', 
            'update_version'],

        2: ['ask_inputs',
            'learn_owner_repo',
            'get_response',
            'download',
            'save_credentials',
            'verify_sha',
            'update_version'],

        3: ['get_response',
            'download',
            'backup_old_appimage',
            'verify_sha',
            'update_version'],

        4: ['get_response',
            'download', 
            'verify_sha',
            'update_version']
    }

    # Ask the user for their choice
    print("Welcome to the my-unicorn 🦄!")
    print("Choose one of the following options:")
    print("====================================")
    print("1. Update existing appimage")
    print("2. Download new appimage")
    print("3. Update json file")
    print("4. Exit")
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
