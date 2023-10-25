import sys
import logging
import requests

def handle_common_errors(func):
    """Handle common errors"""
    def wrapper(self):
        try:
            return func(self)
        except ValueError as value_e:
            logging.error(f"An error occured in {func.__name__}: {str(value_e)}", exc_info=True)
            print("\033[41;30mInvalid input or value error. Try again.\033[0m")
            sys.exit()
        except KeyboardInterrupt as keyboard_e:
            logging.error(f"An error occured in {func.__name__}: {str(keyboard_e)}", exc_info=True)
            print("\033[41;30mKeyboard interrupt. Exiting...\033[0m")
            sys.exit()
        except EOFError as eof_e:
            logging.error(f"An error occured in {func.__name__}: {str(eof_e)}", exc_info=True)
            print("\033[41;30mEOF error. Input cannot be empty.\033[0m")
            sys.exit()
        except KeyError as key_e:
            logging.error(f"An error occured in {func.__name__}: {str(key_e)}", exc_info=True)
            print("\033[41;30mKey error. The key doesn't exist.\033[0m")
            sys.exit()
        except FileNotFoundError as file_e:
            logging.error(f"An error occured in {func.__name__}: {str(file_e)}", exc_info=True)
            print("\033[41;30mFile not found error.\033[0m")
            sys.exit()
        except Exception as error:
            logging.error(f"An unknown error occured in {func.__name__}: {str(error)}", exc_info=True)
            print("\033[41;30mAn unknown error occurred.\033[0m")
            print(f"Error: {error}")
            sys.exit()
    return wrapper

def handle_api_errors(func):
    """Handle the api errors"""
    def wrapper(self):
        try:
            return func(self)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.RequestException, requests.exceptions.HTTPError,) as error:
            logging.error(f"An error occured in {func.__name__}: {str(error)}", exc_info=True)
            print("\033[41;30mAn error occurred while handling api errors")
            print(f"Error: {error}")
            sys.exit()
        except Exception as error:
            logging.error(f"An unknown error occured in {func.__name__}: {str(error)}", exc_info=True)
            print("\033[41;30mAn unknown error occurred.\033[0m")
            print(f"Error: {error}")
            sys.exit()
    return wrapper