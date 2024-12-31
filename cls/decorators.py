import sys
import logging
import requests

# Set up logging
logging.basicConfig(level=logging.ERROR)


def handle_error(func_name, error, exit_message):
    """Handle the error by logging it and printing an exit message."""
    logging.error(f"An error occurred in {func_name}: {str(error)}", exc_info=True)
    print(f"\033[41;30m{exit_message}\033[0m")
    sys.exit()


def handle_common_errors(func):
    """Handle common errors."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as error:
            handle_error(
                func.__name__, error, "Invalid input or value error. Try again."
            )
        except KeyboardInterrupt as error:
            handle_error(func.__name__, error, "Keyboard interrupt. Exiting...")
        except EOFError as error:
            handle_error(func.__name__, error, "EOF error. Input cannot be empty.")
        except KeyError as error:
            handle_error(func.__name__, error, "Key error. The key doesn't exist.")
        except FileNotFoundError as error:
            handle_error(func.__name__, error, "File not found error.")
        except Exception as error:
            handle_error(func.__name__, error, "An unknown error occurred.")

    return wrapper


def handle_api_errors(func):
    """Handle the API-related errors."""

    def wrapper(*args, **kwargs):
        try:
            response = func(*args, **kwargs)
            return response
        except requests.exceptions.TooManyRedirects as error:
            handle_error(func.__name__, error, "Too many redirects. Try again.")
        except requests.exceptions.InvalidURL as error:
            handle_error(func.__name__, error, "Invalid URL. Try again.")
        except requests.exceptions.Timeout as error:
            handle_error(func.__name__, error, "Timeout error. Try again.")
        except requests.exceptions.ConnectionError as error:
            handle_error(func.__name__, error, "Connection error. Try again.")
        except requests.exceptions.RequestException as error:
            handle_error(func.__name__, error, "Request error. Try again.")
        except requests.exceptions.HTTPError as error:
            logging.error(
                f"An error occurred in {func.__name__}: {str(error)}", exc_info=True
            )
            print("+" + "-" * 50 + "+")
            print("|" + " " * 50 + "|")
            print("\033[41;30mHTTP error. Try again.\033[0m")
            print("|" + " " * 50 + "|")
            print("+" + "-" * 50 + "+")
            return response
        except Exception as error:
            handle_error(func.__name__, error, "An unknown error occurred.")

    return wrapper
