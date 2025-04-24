#!/usr/bin/python3
"""Main module for my-unicorn CLI application.
This module configures logging, loads configuration files, and executes commands."""

import gettext
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from src.commands.customize_app_config import CustomizeAppConfigCommand
from src.commands.customize_global_config import CustomizeGlobalConfigCommand
from src.commands.download import DownloadCommand
from src.commands.invoker import CommandInvoker
from src.commands.manage_token import ManageTokenCommand
from src.commands.migrate_config import MigrateConfigCommand
from src.commands.update_all_auto import UpdateAllAutoCommand
from src.commands.update_all_async import UpdateAsyncCommand
from src.commands.delete_backups import DeleteBackupsCommand
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.auth_manager import GitHubAuthManager

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

_ = gettext.gettext


def custom_excepthook(exc_type, exc_value, exc_traceback):
    """Custom excepthook to log uncaught exceptions"""
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def get_user_choice() -> int:
    """Display menu and get user choice using Rich library with side-by-side layout.

    Returns:
        int: The user's menu choice as an integer

    Raises:
        ValueError: If user input cannot be converted to an integer
        KeyboardInterrupt: If user cancels with Ctrl+C
    """
    console.print(
        Panel.fit(
            "[bold cyan]Welcome to my-unicorn[/bold cyan] :unicorn:",
            border_style="cyan",
            title="🦄",
        )
    )

    # Display GitHub API rate limit info if available
    try:
        remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

        # Create a status table for API rate limit information
        status_table = Table(box=box.ROUNDED, border_style="blue", show_header=False, expand=False)
        status_table.add_column("Status", style="dim blue", justify="right")
        status_table.add_column("Value", style="green")

        if is_authenticated:
            status_table.add_row(
                "GitHub API Status", f"[green]{remaining}[/green] of {limit} requests remaining"
            )
            status_table.add_row("Authentication", "✅ Authenticated")
            status_table.add_row("Reset Time", f"{reset_time}")

            if remaining < 100:
                status_table.add_row("Warning", f"[yellow]⚠️ Low API requests remaining![/yellow]")
        else:
            status_table.add_row(
                "GitHub API Status", f"[yellow]{remaining} of 60 requests remaining[/yellow]"
            )
            status_table.add_row("Authentication", "❌ Unauthenticated")
            status_table.add_row(
                "Note", "[blue]🔑 Add token (option 6) for 5000 requests/hour[/blue]"
            )

        console.print(status_table)
    except Exception as e:
        logging.debug(f"Error checking rate limits: {e}")

    # Create layout grid with three equally sized columns
    layout = Table.grid(expand=True)
    layout.add_column(ratio=1)
    layout.add_column(ratio=1)
    layout.add_column(ratio=1)

    # Download & Update panel
    download_table = Table(
        box=box.ROUNDED,
        show_header=False,
        border_style="magenta",
        title="[bold magenta]Download & Update[/bold magenta]",
    )
    download_table.add_column("Option", style="cyan", justify="right", width=2)
    download_table.add_column("Description")
    download_table.add_row("1", "Download new AppImage")
    download_table.add_row("2", "Update all AppImages")
    download_table.add_row("3", "Select AppImages to update")

    # Configuration panel
    config_table = Table(
        box=box.ROUNDED,
        show_header=False,
        border_style="blue",
        title="[bold blue]Configuration[/bold blue]",
    )
    config_table.add_column("Option", style="cyan", justify="right", width=2)
    config_table.add_column("Description")
    config_table.add_row("4", "Manage AppImage settings")
    config_table.add_row("5", "Manage global settings")
    config_table.add_row("6", "Manage GitHub token")

    # Maintenance panel
    maint_table = Table(
        box=box.ROUNDED,
        show_header=False,
        border_style="green",
        title="[bold green]Maintenance[/bold green]",
    )
    maint_table.add_column("Option", style="cyan", justify="right", width=2)
    maint_table.add_column("Description")
    maint_table.add_row("7", "Update configuration files")
    maint_table.add_row("8", "Clean old backups")
    maint_table.add_row("9", "Exit")

    # Add tables to layout grid
    layout.add_row(download_table, config_table, maint_table)

    # Print the layout
    console.print(layout)

    try:
        choice = console.input("[bold cyan]Enter your choice:[/bold cyan] ")
        return int(choice)
    except ValueError as error:
        console.print(f"[bold red]Invalid input: {error}[/bold red]")
        logging.error(f"Invalid menu choice: {error}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("User interrupted the program with Ctrl+C")
        console.print("\n[yellow]Program interrupted. Exiting gracefully...[/yellow]")
        sys.exit(0)


def configure_logging():
    """Configure logging for the application."""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = "my-unicorn.log"
    log_file_path = os.path.join(log_dir, log_file)

    # Configure file handler for all log levels
    file_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=3)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # Changed to DEBUG level

    # Configure console handler for ERROR and above only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)  # Only show errors and above in console
    console_formatter = logging.Formatter("%(message)s")  # Simpler format for console
    console_handler.setFormatter(console_formatter)

    # Get root logger and configure it
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Changed to DEBUG level

    # Remove any existing handlers (in case this function is called multiple times)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add the configured handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info("Logging configured with DEBUG level")


def main():
    configure_logging()

    # Config Initialize, global config auto loads the config file
    # Commands create the config file if it doesn't exist
    global_config = GlobalConfigManager()
    app_config = AppConfigManager()

    # # Instantiate LocaleManager and set locale
    # locale_manager = LocaleManager()
    # locale_manager.load_translations(global_config.locale)

    # Initialize CommandInvoker and register commands
    invoker = CommandInvoker()

    invoker.register_command(1, DownloadCommand())
    invoker.register_command(2, UpdateAllAutoCommand())
    invoker.register_command(3, UpdateAsyncCommand())  # Register the new async update command
    invoker.register_command(4, CustomizeAppConfigCommand())
    invoker.register_command(5, CustomizeGlobalConfigCommand())
    invoker.register_command(6, ManageTokenCommand())
    invoker.register_command(7, MigrateConfigCommand())
    invoker.register_command(8, DeleteBackupsCommand())

    # Main menu loop
    while True:
        choice = get_user_choice()
        if choice == 9:  # Updated exit option number
            logging.info("User selected to exit application")
            print("Exiting...")
            sys.exit(0)
        invoker.execute_command(choice)


if __name__ == "__main__":
    sys.excepthook = custom_excepthook
    main()
