#!/usr/bin/python3
import sys
from classes.FileHandler import FileHandler

def main():
    """Create an instance of FileHandler and call the methods. 
    The methods are called based on the user's choice.    
    """
    file_handler = FileHandler()

    functions = {
        1: ['ask_inputs', 'learn_owner_repo', 'download',
           'save_credentials', 'verify_sha', 'backup_old_appimage'],
        2: ['ask_inputs', 'learn_owner_repo', 'download', 'save_credentials', 'verify_sha'],
        3: ['update_json', 'download', 'verify_sha', 'backup_old_appimage'],
        4: ['update_json', 'download', 'verify_sha']
    }

    print("Welcome to the my-unicorn 🦄!")
    print("Choose one of the following options:")
    print("1. Update appimage from JSON file")
    print("2. Download new appimage")
    print("3. Exit")
    choice = int(input("Enter your choice: "))
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
        file_handler.ask_inputs()
        for function in functions[choice]:
            if function in dir(file_handler):
                method = getattr(file_handler, function)
                method()
            else:
                print(f"Function {function} not found")
    elif choice == 3:
        print("Exiting...")
        sys.exit()
    else:
        print("Invalid choice")
        sys.exit()


if __name__ == "__main__":
    main()
