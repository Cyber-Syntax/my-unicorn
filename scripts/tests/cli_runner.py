"""CLI command runner and app management utilities.

This module provides functions to execute my-unicorn CLI commands
and manage app lifecycle (install, remove, etc.).

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger("my-unicorn-test")

# Global test mode ("production" or "development")
_TEST_MODE = "development"
local_bin_my_unicorn = Path.home() / ".local" / "bin" / "my-unicorn"


def set_test_mode(mode: str) -> None:
    """Set the test mode for CLI execution.

    Args:
        mode: Test mode ("production" or "development")
    """
    global _TEST_MODE
    if mode not in ["production", "development"]:
        msg = f"Invalid mode: {mode}. Must be 'production' or 'development'"
        raise ValueError(msg)
    _TEST_MODE = mode
    logger.debug("Test mode set to: %s", mode)


def get_test_mode() -> str:
    """Get the current test mode.

    Returns:
        Current test mode ("production" or "development")
    """
    return _TEST_MODE


def get_current_version() -> str:
    """Get the current my-unicorn version.

    Returns:
        Current version string
    """
    try:
        result = subprocess.run(
            ["/usr/bin/uv", "run", "my-unicorn", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split()[-1]
    except Exception:
        return "unknown"


def get_production_current_version() -> str:
    """Get the current my-unicorn version in production mode.

    Returns:
        Current version string
    """
    try:
        result = subprocess.run(
            [str(local_bin_my_unicorn), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split()[-1]
    except Exception:
        return "unknown"


def run_cli(
    *args: str, track_network: bool = False
) -> (
    subprocess.CompletedProcess[str]
    | tuple[subprocess.CompletedProcess[str], dict[str, Any]]
):
    """Run my-unicorn CLI command.

    Uses the mode set by set_test_mode() to determine command execution.

    Args:
        *args: Command line arguments to pass to my-unicorn
        track_network: Whether to track network I/O during execution

    Returns:
        If track_network=False: CompletedProcess instance
        If track_network=True: Tuple of (CompletedProcess, network_stats dict)

    Raises:
        subprocess.CalledProcessError: If command fails
    """
    env = os.environ.copy()
    env["CI"] = "true"

    # Determine command based on test mode
    if _TEST_MODE == "production":
        cmd = [str(local_bin_my_unicorn), *args]
    else:  # development mode
        cmd = ["uv", "run", "my-unicorn", *args]

    logger.debug("Running command (%s mode): %s", _TEST_MODE, " ".join(cmd))

    # Track network I/O if requested
    network_stats: dict[str, Any] = {}
    if track_network:
        try:
            # Get initial network counters
            net_io_start = psutil.net_io_counters()
            start_time = time.perf_counter()

            result = subprocess.run(
                cmd,
                text=True,
                check=False,
                env=env,
            )

            # Calculate network I/O and time
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            net_io_end = psutil.net_io_counters()

            bytes_sent = net_io_end.bytes_sent - net_io_start.bytes_sent
            bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
            total_bytes = bytes_sent + bytes_recv

            # Estimate network time based on I/O (rough heuristic)
            # Assume if significant network activity occurred, attribute time
            network_time_ms = 0.0
            if total_bytes > 1024:  # More than 1KB transferred
                # Estimate: if we transferred data, assume some network latency
                # This is a rough estimate - actual network time is hard to measure
                # without deep packet inspection or instrumentation
                network_time_ms = min(
                    elapsed_ms * 0.7, elapsed_ms
                )  # Max 70% of total time

            network_stats = {
                "bytes_sent": bytes_sent,
                "bytes_received": bytes_recv,
                "total_bytes": total_bytes,
                "network_time_ms": network_time_ms,
                "total_time_ms": elapsed_ms,
            }

        except Exception as e:
            logger.warning("Failed to track network I/O: %s", e)
            result = subprocess.run(
                cmd,
                text=True,
                check=False,
                env=env,
            )
            network_stats = {"error": str(e), "network_time_ms": 0.0}
    else:
        result = subprocess.run(
            cmd,
            text=True,
            check=False,
            env=env,
        )

    if result.returncode != 0:
        logger.error("Command failed with exit code %s", result.returncode)

    if track_network:
        return result, network_stats
    return result


def remove_apps(*app_names: str) -> None:
    """Remove apps using my-unicorn remove command.

    Args:
        *app_names: Names of apps to remove
    """
    if not app_names:
        return

    logger.info("Removing apps: %s", ", ".join(app_names))
    result = run_cli("remove", *app_names)

    # Don't fail on remove errors (app might not be installed)
    if result.returncode != 0:
        logger.warning(
            "Remove command completed with errors (may be expected)"
        )


# Module constants
APP_ROOT = Path(__file__).parent.parent.resolve()
MY_UNICORN_VERSION = get_current_version()
MY_UNICORN_PROD_VERSION = get_production_current_version()
