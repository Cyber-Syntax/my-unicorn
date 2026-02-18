"""Sandbox environment manager for isolated E2E test execution.

This module provides the SandboxEnvironment class which creates and manages
temporary HOME directories for test execution, protecting real user
configurations.
"""

import configparser
import os
import shutil
import tempfile
import types
from pathlib import Path


class SandboxEnvironment:
    """Manages a temporary sandbox environment for CLI testing.

    Provides isolation from real user configurations by:
    - Creating a temporary HOME directory
    - Creating default settings (no copying - simulates fresh install)
    - Cleaning up on exit (optional)

    Attributes:
        temp_home: Path to the temporary HOME directory
        cleanup_on_exit: Whether to cleanup temp directory on exit
        original_home: Original HOME environment variable value
        original_env: Original environment variables before sandbox activation
    """

    def __init__(
        self,
        name: str = "sandbox",
        cleanup: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Initialize the sandbox environment manager.

        Creates temporary directory but does not activate it yet.
        Use as context manager to activate: `with SandboxEnvironment() as sb:`

        Args:
            name: Meaningful name for the sandbox folder
                  (default: "sandbox")
                  Creates /tmp/my-unicorn-e2e-{name}/ directory
            cleanup: If True, removes temp directory on exit.
                     If False, keeps it for manual inspection
                     (default: False)
        """
        # Create consistent, meaningful temp directory name
        temp_dir = Path(tempfile.gettempdir()) / f"my-unicorn-e2e-{name}"

        # Clean up if already exists (from previous failed test)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Create fresh temp directory
        temp_dir.mkdir(parents=True, exist_ok=True)

        self.temp_home = temp_dir
        self.cleanup_on_exit = cleanup
        self.original_home = os.environ.get("HOME")
        self.original_env: dict[str, str | None] = {}

    def __enter__(self) -> "SandboxEnvironment":
        """Enter context manager: activate sandbox environment.

        Steps:
        - Ensure .config/my-unicorn directory exists
        - Create default settings (no config copying - fresh install)
        - Set HOME environment variable to sandbox
        - CLI will create apps, cache, logs from scratch

        Returns:
            Self for use in context manager
        """
        # Create base config directory structure
        config_dir = self.temp_home / ".config" / "my-unicorn"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Create default settings (no copying - simulate fresh install)
        self._create_default_settings()

        # Set environment variables
        self.original_env["HOME"] = os.environ.get("HOME")
        os.environ["HOME"] = str(self.temp_home)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit context manager: cleanup sandbox environment.

        Steps:
        - Restore original HOME environment variable
        - Remove temporary directory (only if cleanup=True)

        Args:
            exc_type: Exception type if raised in context
            exc_val: Exception value if raised in context
            exc_tb: Exception traceback if raised in context
        """
        # Restore original environment
        if "HOME" in self.original_env:
            if self.original_env["HOME"] is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = self.original_env["HOME"]

        # Remove temporary directory (only if cleanup=True)
        if self.cleanup_on_exit:
            self._cleanup()

    def _copy_real_config(self) -> None:
        """Copy real my-unicorn config from original home to sandbox.

        Copies the entire ~/.config/my-unicorn directory if it exists.
        This includes:
        - settings.conf (global configuration)
        - apps/ directory (per-app state files)
        - cache/ directory (release cache)
        - logs/ directory (application logs)

        If the source doesn't exist, this is a no-op and subsequent
        CLI commands will create defaults inside the sandbox.
        """
        if not self.original_home:
            return

        original_config_dir = (
            Path(self.original_home) / ".config" / "my-unicorn"
        )
        if not original_config_dir.exists():
            return

        target_config_dir = self.temp_home / ".config" / "my-unicorn"
        target_config_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files and directories from source to target
        for item in original_config_dir.iterdir():
            target_item = target_config_dir / item.name
            if item.is_dir():
                if target_item.exists():
                    shutil.rmtree(target_item)
                shutil.copytree(item, target_item)
            else:
                shutil.copy2(item, target_item)

    def _rewrite_config_paths(self) -> None:
        """Rewrite directory paths in settings.conf to point to sandbox.

        Reads settings.conf and updates all directory paths in the [directory]
        section to point to subdirectories within the sandbox temp_home.

        This ensures that even if the original config has absolute paths like
        /home/user/Applications, they will be rewritten to
        /tmp/my-unicorn-e2e-XXX/Applications within the sandbox.

        Directory keys rewritten:
        - download
        - storage
        - backup
        - icon
        - settings
        - logs
        - cache
        """
        settings_file = (
            self.temp_home / ".config" / "my-unicorn" / "settings.conf"
        )

        # Create default settings.conf if it doesn't exist
        if not settings_file.exists():
            self._create_default_settings()
            return

        # Read and parse the config file
        config = configparser.ConfigParser()
        config.read(settings_file)

        # Rewrite directory paths
        directory_keys = [
            "download",
            "storage",
            "backup",
            "icon",
            "settings",
            "logs",
            "cache",
        ]

        if not config.has_section("directory"):
            config.add_section("directory")

        for key in directory_keys:
            # Create a default path in sandbox if not present
            if not config.has_option("directory", key):
                # Map directory keys to sandbox subdirectories
                subdir_map = {
                    "download": "Downloads",
                    "storage": "Applications",
                    "backup": "Applications/backups",
                    "icon": "Applications/icons",
                    "settings": ".config/my-unicorn",
                    "logs": ".config/my-unicorn/logs",
                    "cache": ".config/my-unicorn/cache",
                }
                subdir = subdir_map.get(key, key)
                new_path = self.temp_home / subdir
            else:
                # Get existing path and create it in sandbox
                old_value = config.get("directory", key)
                # Strip any inline comments
                old_value = old_value.split("#")[0].strip()

                # Convert to absolute path (handle ~)
                old_path = Path(old_value).expanduser()

                # Determine relative directory name
                if key in ("logs", "cache", "settings"):
                    # These are typically under .config/my-unicorn
                    new_path = self.temp_home / ".config" / "my-unicorn" / key
                elif key == "backup":
                    new_path = self.temp_home / "Applications" / "backups"
                elif key == "icon":
                    new_path = self.temp_home / "Applications" / "icons"
                elif key in ("storage", "download"):
                    # Use parent directory name if available
                    subdir = old_path.name if old_path.name else key
                    new_path = self.temp_home / subdir
                else:
                    new_path = self.temp_home / key

            # Create the directory
            new_path.mkdir(parents=True, exist_ok=True)

            # Update config
            config.set("directory", key, str(new_path))

        # Write the updated config back
        with settings_file.open("w") as f:
            config.write(f)

    def _create_default_settings(self) -> None:
        """Create a default settings.conf in the sandbox.

        This is used when no real config exists. Creates a minimal
        valid settings.conf with all paths pointing to sandbox directories.
        """
        settings_file = (
            self.temp_home / ".config" / "my-unicorn" / "settings.conf"
        )

        config = configparser.ConfigParser()
        config["DEFAULT"] = {
            "config_version": "1.1.0",
            "max_concurrent_downloads": "5",
            "max_backup": "1",
            "log_level": "INFO",
            "console_log_level": "INFO",
        }

        config["network"] = {
            "retry_attempts": "3",
            "timeout_seconds": "10",
        }

        config["directory"] = {
            "download": str(self.temp_home / "Downloads"),
            "storage": str(self.temp_home / "Applications"),
            "backup": str(self.temp_home / "Applications" / "backups"),
            "icon": str(self.temp_home / "Applications" / "icons"),
            "settings": str(self.temp_home / ".config" / "my-unicorn"),
            "logs": str(self.temp_home / ".config" / "my-unicorn" / "logs"),
            "cache": str(self.temp_home / ".config" / "my-unicorn" / "cache"),
        }

        # Create directories
        for dir_path in config["directory"].values():
            Path(dir_path).mkdir(parents=True, exist_ok=True)

        # Write config
        with settings_file.open("w") as f:
            config.write(f)

    def _cleanup(self) -> None:
        """Remove temporary directory and all contents.

        Safely removes the entire sandbox directory tree.
        """
        if self.temp_home.exists():
            shutil.rmtree(self.temp_home, ignore_errors=True)
