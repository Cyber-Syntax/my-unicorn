"""E2E CLI runner for executing my-unicorn commands in sandbox.

This module provides the E2ERunner class which executes my-unicorn CLI
commands in a sandboxed environment, with utilities for config manipulation.
"""

import json
import os
import subprocess

from tests.e2e.sandbox import SandboxEnvironment


class E2ERunner:
    """Executes my-unicorn CLI commands in sandboxed environment.

    Provides methods for running CLI commands and manipulating app configs
    within the sandbox's isolated environment.

    Attributes:
        sandbox: The SandboxEnvironment instance for this runner
    """

    def __init__(self, sandbox: SandboxEnvironment) -> None:
        """Initialize the E2E CLI runner.

        Args:
            sandbox: Active SandboxEnvironment instance (should be in context)
        """
        self.sandbox = sandbox

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Execute a my-unicorn CLI command in sandbox.

        Runs the command with the sandbox's HOME environment variable set.

        Args:
            *args: Command line arguments to pass to my-unicorn

        Returns:
            CompletedProcess instance with command result
        """
        # Build the command using uv run (executing from source)
        cmd = ["uv", "run", "my-unicorn", *args]

        # Set up environment with sandbox HOME
        env = os.environ.copy()
        env["HOME"] = str(self.sandbox.temp_home)

        # Execute the command (nosec: cmd solely from arguments)
        return subprocess.run(  # noqa: S603
            cmd,
            text=True,
            check=False,
            env=env,
            capture_output=True,
        )

    def install(
        self, app_name: str, *args: str
    ) -> subprocess.CompletedProcess[str]:
        """Install an app using the install command.

        Args:
            app_name: Name of the app to install
            *args: Additional arguments to pass to install command

        Returns:
            CompletedProcess instance with command result
        """
        return self.run_cli("install", app_name, *args)

    def remove(
        self, app_name: str, *args: str
    ) -> subprocess.CompletedProcess[str]:
        """Remove an installed app.

        Args:
            app_name: Name of the app to remove
            *args: Additional arguments to pass to remove command

        Returns:
            CompletedProcess instance with command result
        """
        return self.run_cli("remove", app_name, *args)

    def update(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Update apps.

        Args:
            *args: Arguments to pass to update command

        Returns:
            CompletedProcess instance with command result
        """
        return self.run_cli("update", *args)

    def set_version(self, app_name: str, version: str) -> None:
        """Modify the installed_version field in app config JSON.

        Reads the app's config file from
        ~/.config/my-unicorn/apps/<app-name>.json, updates the version field
        in state, and writes it back.

        Args:
            app_name: Name of the installed app
            version: New version to set

        Raises:
            FileNotFoundError: If app config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        config_path = (
            self.sandbox.temp_home
            / ".config"
            / "my-unicorn"
            / "apps"
            / f"{app_name}.json"
        )

        if not config_path.exists():
            msg = f"App config not found: {config_path}"
            raise FileNotFoundError(msg)

        # Read the config
        config_text = config_path.read_text()
        config = json.loads(config_text)

        # Update the version in state
        if "state" not in config:
            config["state"] = {}
        config["state"]["version"] = version

        # Write back to file
        config_path.write_text(json.dumps(config, indent=2))
