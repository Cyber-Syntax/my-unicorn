import json
import logging
import os
from dataclasses import dataclass, field


@dataclass
class GlobalConfigManager:
    """Manages global configuration settings."""

    config_file: str = field(default="~/.config/myunicorn/settings.json")
    appimage_download_folder_path: str = field(default_factory=lambda: "~/Documents/appimages")
    appimage_download_backup_folder_path: str = field(
        default_factory=lambda: "~/Documents/appimages/backups"
    )
    keep_backup: bool = field(default=True)
    max_backups: int = field(default=3)  # Number of backups to keep per app
    batch_mode: bool = field(default=False)
    locale: str = field(default="en")
    max_concurrent_updates: int = field(default=3)  # Default value for maximum concurrent updates

    def __post_init__(self):
        # Expand only the config file path during initialization
        self.config_file = os.path.expanduser(self.config_file)
        # Ensure the XDG config directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        self.load_config()

    def expanded_path(self, path):
        """Expand and return a user path."""
        return os.path.expanduser(path)

    def load_config(self):
        """Load global settings from a JSON file or initialize defaults."""
        if os.path.isfile(self.config_file):  # Check if file exists
            try:
                with open(self.config_file, "r", encoding="utf-8") as file:
                    config = json.load(file)

                    # Get all expected config keys from to_dict method
                    expected_keys = set(self.to_dict().keys())
                    found_keys = set(config.keys())

                    # Load each configuration item safely
                    self.appimage_download_folder_path = config.get(
                        "appimage_download_folder_path",
                        self.appimage_download_folder_path,
                    )
                    self.appimage_download_backup_folder_path = config.get(
                        "appimage_download_backup_folder_path",
                        self.appimage_download_backup_folder_path,
                    )
                    self.keep_backup = config.get("keep_backup", self.keep_backup)
                    self.max_backups = config.get("max_backups", self.max_backups)
                    self.batch_mode = config.get("batch_mode", self.batch_mode)
                    self.locale = config.get("locale", self.locale)
                    self.max_concurrent_updates = config.get(
                        "max_concurrent_updates", self.max_concurrent_updates
                    )

                    # If any expected keys are missing, log it
                    missing_keys = expected_keys - found_keys
                    if missing_keys:
                        logging.info(f"Config file is missing keys: {missing_keys}")
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse the configuration file: {e}")
                raise ValueError("Invalid JSON format in the configuration file.")
        else:
            logging.info(f"Configuration file not found at {self.config_file}. Creating one...")
            self.create_global_config()
            return False

        return True

    def to_dict(self):
        """Convert the dataclass to a dictionary."""
        return {
            "appimage_download_folder_path": self.appimage_download_folder_path,
            "appimage_download_backup_folder_path": self.appimage_download_backup_folder_path,
            "keep_backup": self.keep_backup,
            "max_backups": self.max_backups,
            "batch_mode": self.batch_mode,
            "locale": self.locale,
            "max_concurrent_updates": self.max_concurrent_updates,
        }

    def create_global_config(self):
        """Sets up global configuration interactively."""
        print("Setting up global configuration...")

        try:
            # Use default values if input is blank
            appimage_download_folder_path = (
                input(
                    "Enter the folder path to save appimages (default: '~/Documents/appimages'): "
                ).strip()
                or "~/Documents/appimages"
            )
            keep_backup = (
                input("Enable backup for old appimages? (yes/no, default: yes): ").strip().lower()
                or "yes"
            )
            max_backups = (
                input("Max number of backups to keep per app (default: 3): ").strip() or "3"
            )
            batch_mode = input("Enable batch mode? (yes/no, default: no): ").strip().lower() or "no"
            locale = input("Select your locale (en/tr, default: en): ").strip() or "en"
            max_concurrent_updates = (
                input("Max number of concurrent updates (default: 3): ").strip() or "3"
            )

            # Update current instance values
            self.appimage_download_folder_path = appimage_download_folder_path
            self.appimage_download_backup_folder_path = "~/Documents/appimages/backups"
            self.keep_backup = keep_backup == "yes"
            self.max_backups = int(max_backups)
            self.batch_mode = batch_mode == "yes"
            self.locale = locale
            self.max_concurrent_updates = int(max_concurrent_updates)

            # Save the configuration
            self.save_config()
            print("Global configuration saved successfully!")
        except KeyboardInterrupt:
            logging.info("Global configuration setup interrupted by user")
            print("\nConfiguration setup interrupted. Using default values.")

            # Set default values
            self.appimage_download_folder_path = "~/Documents/appimages"
            self.appimage_download_backup_folder_path = "~/Documents/appimages/backups"
            self.keep_backup = True
            self.max_backups = 3
            self.batch_mode = False
            self.locale = "en"
            self.max_concurrent_updates = 3

            # Save the default configuration
            self.save_config()
            print("Default global configuration saved.")

    def save_config(self):
        """Save global settings to a JSON file."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)
        logging.info(f"Global configuration saved to {self.config_file}")

    # Properties to access expanded paths on demand
    @property
    def expanded_appimage_download_folder_path(self):
        return os.path.expanduser(self.appimage_download_folder_path)

    @property
    def expanded_appimage_download_backup_folder_path(self):
        return os.path.expanduser(self.appimage_download_backup_folder_path)

    def customize_global_config(self):
        """Customize the configuration settings for the Global Config."""
        self.load_config()

        # Initialize Rich console if not already imported
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            from rich import box

            console = Console()
        except ImportError:
            logging.error("Rich library not available for enhanced display")
            self._fallback_customize_config()
            return

        console.print(
            Panel.fit(
                "[bold cyan]Global Configuration Settings[/bold cyan]",
                border_style="cyan",
                title="⚙️",
            )
        )

        # Create configuration status table with centered alignment
        status_table = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
        status_table.add_column("Setting", style="dim blue", justify="left")
        status_table.add_column("Value", style="green", justify="left")

        # Add current configuration values to status table
        status_table.add_row("AppImage Download Folder", f"📁 {self.appimage_download_folder_path}")
        status_table.add_row("Backup Folder", f"📁 {self.appimage_download_backup_folder_path}")
        status_table.add_row("Keep Backups", "✅ Yes" if self.keep_backup else "❌ No")
        status_table.add_row("Max Backups Per App", f"📊 {self.max_backups}")
        status_table.add_row("Batch Mode", "✅ Enabled" if self.batch_mode else "❌ Disabled")
        status_table.add_row("Locale", f"🌐 {self.locale}")
        status_table.add_row("Max Concurrent Updates", f"⚡ {self.max_concurrent_updates}")

        # Show configuration status
        console.print(status_table, justify="left")

        # Create layout grid with two equally sized columns
        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)
        layout.add_column(ratio=1)

        # Core Settings panel
        core_table = Table(
            box=box.ROUNDED,
            show_header=False,
            border_style="blue",
            title="[bold blue]Core Settings[/bold blue]",
        )
        core_table.add_column("Option", style="cyan", justify="right", width=2)
        core_table.add_column("Description")
        core_table.add_row("1", "AppImage Download Folder")
        core_table.add_row("2", "Enable Backup")
        core_table.add_row("3", "Max Backups Per App")
        core_table.add_row("4", "Batch Mode")

        # Advanced Settings panel
        advanced_table = Table(
            box=box.ROUNDED,
            show_header=False,
            border_style="green",
            title="[bold green]Advanced Settings[/bold green]",
        )
        advanced_table.add_column("Option", style="cyan", justify="right", width=2)
        advanced_table.add_column("Description")
        advanced_table.add_row("5", "Locale")
        advanced_table.add_row("6", "Max Concurrent Updates")
        advanced_table.add_row("7", "Exit")

        # Add tables to layout grid
        layout.add_row(core_table, advanced_table)

        # Print the layout
        console.print(layout)

        try:
            while True:
                choice = console.input("[bold cyan]Enter your choice (1-7):[/bold cyan] ")
                if choice.isdigit() and 1 <= int(choice) <= 7:
                    break
                else:
                    console.print(
                        "[bold red]Invalid choice, please enter a number between 1 and 7.[/bold red]"
                    )

            if choice == "7":
                console.print("[yellow]Exiting without changes.[/yellow]")
                return

            config_dict = {
                "appimage_download_folder_path": self.appimage_download_folder_path,
                "keep_backup": self.keep_backup,
                "max_backups": self.max_backups,
                "batch_mode": self.batch_mode,
                "locale": self.locale,
                "max_concurrent_updates": self.max_concurrent_updates,
            }
            key = list(config_dict.keys())[int(choice) - 1]

            try:
                if key == "appimage_download_folder_path":
                    new_value = (
                        console.input(
                            "[cyan]Enter the new folder path to save appimages:[/cyan] "
                        ).strip()
                        or "~/Documents/appimages"
                    )
                elif key == "keep_backup":
                    new_value = (
                        console.input("[cyan]Enable backup for old appimages? (yes/no):[/cyan] ")
                        .strip()
                        .lower()
                        or "no"
                    )
                    new_value = new_value == "yes"
                elif key == "max_backups":
                    new_value_str = (
                        console.input(
                            "[cyan]Enter max number of backups to keep per app:[/cyan] "
                        ).strip()
                        or "3"
                    )
                    try:
                        new_value = int(new_value_str)
                        if new_value < 1:
                            console.print(
                                "[yellow]Value must be at least 1. Setting to 1.[/yellow]"
                            )
                            new_value = 1
                    except ValueError:
                        console.print("[yellow]Invalid number. Setting to default (3).[/yellow]")
                        new_value = 3
                elif key == "batch_mode":
                    new_value = (
                        console.input("[cyan]Enable batch mode? (yes/no):[/cyan] ").strip().lower()
                        or "no"
                    )
                    new_value = new_value == "yes"
                elif key == "locale":
                    new_value = (
                        console.input(
                            "[cyan]Select your locale (en/tr, default: en):[/cyan] "
                        ).strip()
                        or "en"
                    )
                elif key == "max_concurrent_updates":
                    new_value_str = (
                        console.input(
                            "[cyan]Enter max number of concurrent updates:[/cyan] "
                        ).strip()
                        or "3"
                    )
                    try:
                        new_value = int(new_value_str)
                        if new_value < 1:
                            console.print(
                                "[yellow]Value must be at least 1. Setting to 1.[/yellow]"
                            )
                            new_value = 1
                    except ValueError:
                        console.print("[yellow]Invalid number. Setting to default (3).[/yellow]")
                        new_value = 3

                setattr(self, key, new_value)
                self.save_config()
                console.print(
                    f"[bold green]✅ {key.replace('_', ' ').title()} updated successfully in settings.json[/bold green]"
                )
                console.print("=================================================")

                # Show updated configuration setting
                console.print(
                    Panel(
                        f"[bold]Updated [cyan]{key.replace('_', ' ').title()}[/cyan] to: [green]{getattr(self, key)}[/green][/bold]",
                        border_style="green",
                    )
                )

            except KeyboardInterrupt:
                logging.info("User interrupted configuration update")
                console.print(
                    "\n[yellow]Configuration update cancelled. No changes were made.[/yellow]"
                )
                return
        except KeyboardInterrupt:
            logging.info("User interrupted configuration customization")
            console.print(
                "\n[yellow]Configuration customization cancelled. No changes were made.[/yellow]"
            )
            return

    def _fallback_customize_config(self):
        """Fallback method for customizing config without Rich library."""
        print("Select which key to modify:")
        print("=================================================")
        print(f"1. AppImage Download Folder: {self.appimage_download_folder_path}")
        print(f"2. Enable Backup: {'Yes' if self.keep_backup else 'No'}")
        print(f"3. Max Backups Per App: {self.max_backups}")
        print(f"4. Batch Mode: {'Yes' if self.batch_mode else 'No'}")
        print(f"5. Locale: {self.locale}")
        print(f"6. Max Concurrent Updates: {self.max_concurrent_updates}")
        print("7. Exit")
        print("=================================================")

        try:
            while True:
                choice = input("Enter your choice: ")
                if choice.isdigit() and 1 <= int(choice) <= 7:
                    break
                else:
                    print("Invalid choice, please enter a number between 1 and 7.")

            if choice == "7":
                print("Exiting without changes.")
                return

            config_dict = {
                "appimage_download_folder_path": self.appimage_download_folder_path,
                "keep_backup": self.keep_backup,
                "max_backups": self.max_backups,
                "batch_mode": self.batch_mode,
                "locale": self.locale,
                "max_concurrent_updates": self.max_concurrent_updates,
            }
            key = list(config_dict.keys())[int(choice) - 1]

            try:
                if key == "appimage_download_folder_path":
                    new_value = (
                        input("Enter the new folder path to save appimages: ").strip()
                        or "~/Documents/appimages"
                    )
                elif key == "keep_backup":
                    new_value = (
                        input("Enable backup for old appimages? (yes/no): ").strip().lower() or "no"
                    )
                    new_value = new_value == "yes"
                elif key == "max_backups":
                    new_value_str = (
                        input("Enter max number of backups to keep per app: ").strip() or "3"
                    )
                    try:
                        new_value = int(new_value_str)
                        if new_value < 1:
                            print("Value must be at least 1. Setting to 1.")
                            new_value = 1
                    except ValueError:
                        print("Invalid number. Setting to default (3).")
                        new_value = 3
                elif key == "batch_mode":
                    new_value = input("Enable batch mode? (yes/no): ").strip().lower() or "no"
                    new_value = new_value == "yes"
                elif key == "locale":
                    new_value = input("Select your locale (en/tr, default: en): ").strip() or "en"
                elif key == "max_concurrent_updates":
                    new_value_str = input("Enter max number of concurrent updates: ").strip() or "3"
                    try:
                        new_value = int(new_value_str)
                        if new_value < 1:
                            print("Value must be at least 1. Setting to 1.")
                            new_value = 1
                    except ValueError:
                        print("Invalid number. Setting to default (3).")
                        new_value = 3

                setattr(self, key, new_value)
                self.save_config()
                print(f"\033[42m{key.capitalize()} updated successfully in settings.json\033[0m")
                print("=================================================")
            except KeyboardInterrupt:
                logging.info("User interrupted configuration update")
                print("\nConfiguration update cancelled. No changes were made.")
                return
        except KeyboardInterrupt:
            logging.info("User interrupted configuration customization")
            print("\nConfiguration customization cancelled. No changes were made.")
            return
