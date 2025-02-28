import logging
import sys

import requests

# Set up logging
logging.basicConfig(level=logging.ERROR)


def handle_error(func_name, error, exit_message):
    """Handle the error by logging it and printing an exit message."""
    logging.error(f"An error occurred in {func_name}: {str(error)}", exc_info=True)
    print(f"\033[41;30m{exit_message}\033[0m")
    sys.exit()


def handle_common_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as error:
            handle_error(
                func.__name__, error, _("Invalid input or value error. Try again.")
            )
        except KeyboardInterrupt as error:
            handle_error(func.__name__, error, _("Keyboard interrupt. Exiting..."))
        except EOFError as error:
            handle_error(func.__name__, error, _("EOF error. Input cannot be empty."))
        except KeyError as error:
            handle_error(func.__name__, error, _("Key error. The key doesn't exist."))
        except FileNotFoundError as error:
            handle_error(func.__name__, error, _("File not found error."))
        except Exception as error:
            handle_error(func.__name__, error, _("An unknown error occurred."))

    return wrapper


def handle_api_errors(func):
    def wrapper(*args, **kwargs):
        try:
            response = func(*args, **kwargs)
            return response
        except requests.exceptions.TooManyRedirects as error:
            handle_error(func.__name__, error, _("Too many redirects. Try again."))
        except requests.exceptions.InvalidURL as error:
            handle_error(func.__name__, error, _("Invalid URL. Try again."))
        except requests.exceptions.Timeout as error:
            handle_error(func.__name__, error, _("Timeout error. Try again."))
        except requests.exceptions.ConnectionError as error:
            handle_error(func.__name__, error, _("Connection error. Try again."))
        except requests.exceptions.RequestException as error:
            handle_error(
                func.__name__,
                error,
                _("Request error. Check network connection and try again."),
            )
        except requests.exceptions.HTTPError as error:
            handle_error(
                func.__name__,
                error,
                _("HTTP error. Check network connection and try again."),
            )

        except Exception as error:
            handle_error(func.__name__, error, _("An unknown error occurred."))

    return wrapper
