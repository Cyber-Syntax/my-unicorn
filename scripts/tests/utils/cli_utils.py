#!/usr/bin/env python3
"""CLI execution utilities for test framework.

This module provides pure functions for executing my-unicorn CLI commands
in both production and development modes.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import os
import subprocess
from pathlib import Path
from typing import Literal


def run_my_unicorn(
    command: str,
    *args: str,
    mode: Literal["development", "production"] = "development",
) -> subprocess.CompletedProcess[str]:
    """Execute my-unicorn CLI command.

    Args:
        command: Command to execute (e.g., "install", "update", "remove")
        *args: Additional command arguments
        mode: Execution mode (development=uv run, production=installed bin)

    Returns:
        CompletedProcess instance with returncode, stdout, stderr

    Examples:
        >>> result = run_my_unicorn("install", "qownnotes", mode="development")
        >>> result = run_my_unicorn("update", mode="production")
    """
    env = os.environ.copy()
    env["CI"] = "true"

    if mode == "production":
        local_bin = Path.home() / ".local" / "bin" / "my-unicorn"
        cmd = [str(local_bin), command, *args]
    else:  # development mode
        cmd = ["uv", "run", "my-unicorn", command, *args]

    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def get_my_unicorn_version(
    mode: Literal["development", "production"] = "development",
) -> str:
    """Get my-unicorn version.

    Args:
        mode: Execution mode

    Returns:
        Version string (e.g., "2.2.1a0"), or unknown if not determinable
    """
    try:
        result = run_my_unicorn("--version", mode=mode)
        if result.returncode == 0:
            # Parse "my-unicorn version 2.2.1a0" -> "2.2.1a0"
            return result.stdout.strip().split()[-1]
        return "unknown"  # noqa: TRY300
    except Exception:  # noqa: BLE001
        return "unknown"


def kill_my_unicorn_processes() -> int:
    """Kill any running my-unicorn processes.

    Returns:
        Number of processes killed
    """
    try:
        result = subprocess.run(
            ["pkill", "-9", "-f", "my-unicorn"],  # noqa: S607
            capture_output=True,
            check=False,
        )
    except Exception:  # noqa: BLE001
        return 0
    # pkill returns 0 if processes killed, 1 if none found
    return 0 if result.returncode == 1 else 1


def is_command_available(command: str) -> bool:
    """Check if a command is available in PATH.

    Args:
        command: Command name to check

    Returns:
        True if command is available, False otherwise
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["which", command],  # noqa: S607
            capture_output=True,
            check=False,
        )
    except Exception:  # noqa: BLE001
        return False
    return result.returncode == 0
