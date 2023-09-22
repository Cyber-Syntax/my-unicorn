#!/usr/bin/python3
import sys
import logging
from cls.FileHandler import FileHandler

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
        1: ['ask_inputs', 'learn_owner_repo', 'download',
           'save_credentials', 'backup_old_appimage', 'verify_sha'],
        2: ['ask_inputs', 'learn_owner_repo', 'download', 'save_credentials', 'verify_sha'],
        3: ['update_json', 'download', 'backup_old_appimage', 'verify_sha'],
        4: ['update_json', 'download', 'verify_sha']
    }

    # Ask the user for their choice
    print("Welcome to the my-unicorn 🦄!")
    print("Choose one of the following options:")
    print("1. Update appimage from JSON file")
    print("2. Download new appimage")
    print("3. Exit")
    try:
        choice = int(input("Enter your choice: "))
    except ValueError as error:
        logging.error(f"Error: {error}", exc_info=True)
        print("Invalid choice. Use 1, 2 or 3.")
    except KeyboardInterrupt as error2:
        logging.error(f"Error: {error2}", exc_info=True)
        print("Keyboard interrupt. Exiting...")
        sys.exit()
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
                # ask user which choice they want to use from functions
                print("Choose one of the following options: \n")
                print("1. Backup old appimage and download new appimage")
                print("2. Download new appimage and overwrite old appimage")
                file_handler.choice = int(input("Enter your choice: "))
                for function in functions[file_handler.choice]:
                    if function in dir(file_handler):
                        method = getattr(file_handler, function)
                        method()
                    else:
                        print(f"Function {function} not found")
                        sys.exit()

            elif choice == 3:
                print("Exiting...")
                sys.exit()
            else:
                print("Invalid choice")
                sys.exit()
        except KeyboardInterrupt as error:
            logging.error(f"Error: {error}", exc_info=True)
            print("Keyboard interrupt. Exiting...")
            sys.exit()

if __name__ == "__main__":
    main()
