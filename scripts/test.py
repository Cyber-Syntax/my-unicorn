#!/usr/bin/env python3
"""Manual test script for my-unicorn.

This script provides comprehensive CLI testing for my-unicorn,
combining URL installs, catalog installs, updates, and all core functionality.

Auto-detects container vs normal machine:
 - In container: uses installed 'my-unicorn' command
 - On normal machine: uses 'uv run my-unicorn' for development

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# ======== Configuration ========

# Get the absolute path to the application root
APP_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_DIR = Path.home() / ".config" / "my-unicorn" / "apps"
LOG_DIR = Path.home() / ".config" / "my-unicorn" / "logs"
LOG_FILE = LOG_DIR / "comprehensive_test.log"

TEST_VERSION = "0.1.0"

# ======== Logging Setup ========


def setup_logging(debug: bool = False) -> logging.Logger:
    """Set up logging configuration with console and file handlers.

    Args:
        debug: Enable debug level logging

    Returns:
        Configured logger instance
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Create logger
    logger = logging.getLogger("my-unicorn-test")
    logger.setLevel(log_level)
    logger.handlers.clear()

    # Create log directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE, mode="w")
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = logging.getLogger("my-unicorn-test")


# ======== Environment Detection ========


def is_container() -> bool:
    """Detect if running inside a container.

    Returns:
        True if running in container, False otherwise
    """
    # Check for container-specific files
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return True

    # Check cgroup for container indicators
    cgroup_file = Path("/proc/1/cgroup")
    if cgroup_file.exists():
        try:
            content = cgroup_file.read_text()
            if any(
                indicator in content
                for indicator in [
                    "docker",
                    "lxc",
                    "containerd",
                    "kubepods",
                    "podman",
                ]
            ):
                return True
        except Exception:
            pass

    # Check for QEMU/KVM virtual machine
    try:
        virt_result = subprocess.run(
            ["/usr/bin/systemd-detect-virt"],
            capture_output=True,
            text=True,
            check=False,
        )
        if virt_result.returncode == 0:
            virt_type = virt_result.stdout.strip()
            if virt_type in ["qemu", "kvm"]:
                lscpu_result = subprocess.run(
                    ["/usr/bin/lscpu"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if (
                    lscpu_result.returncode == 0
                    and "Hypervisor" in lscpu_result.stdout
                ):
                    return True
    except FileNotFoundError:
        pass

    return False


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run my-unicorn CLI command.

    Auto-detects whether to use installed 'my-unicorn' or 'uv run my-unicorn'.

    Args:
        *args: Command line arguments to pass to my-unicorn

    Returns:
        CompletedProcess instance with the command result

    Raises:
        subprocess.CalledProcessError: If command fails
    """
    env = os.environ.copy()
    env["CI"] = "true"

    # Determine command to use
    if is_container():
        # Try installed my-unicorn first
        try:
            subprocess.run(
                ["which", "my-unicorn"],
                capture_output=True,
                check=True,
            )
            cmd = ["my-unicorn", *args]
        except subprocess.CalledProcessError:
            # Fallback to uv run if installed binary not found
            cmd = ["uv", "run", "my-unicorn", *args]
    else:
        cmd = ["uv", "run", "my-unicorn", *args]

    logger.debug("Running command: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        text=True,
        check=False,
        env=env,
    )

    if result.returncode != 0:
        logger.error("Command failed with exit code %s", result.returncode)

    return result


# ======== JSON Config Utilities ========


def set_version(app_name: str, version: str) -> bool:
    """Set app version in config file for update testing.

    Args:
        app_name: Name of the app
        version: Version to set

    Returns:
        True if successful, False otherwise
    """
    config_file = CONFIG_DIR / f"{app_name}.json"

    if not config_file.exists():
        logger.warning(
            "Config not found: %s; skipping version set", config_file
        )
        return False

    try:
        with config_file.open() as f:
            config = json.load(f)

        config["state"]["version"] = version

        with config_file.open("w") as f:
            json.dump(config, f, indent=2)

        logger.info(
            "Set %s version to %s (for update test)", app_name, version
        )
    except Exception:
        logger.exception("Failed to set version for %s", app_name)
        return False
    else:
        return True


# ======== App Management ========


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


# ======== Test Functions ========


def test_url_install(app_name: str, url: str) -> bool:
    """Test installing app via URL.

    Args:
        app_name: Name of the app (for logging)
        url: GitHub URL to install from

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing %s URL install", app_name)
    result = run_cli("install", url)
    return result.returncode == 0


def test_catalog_install(*app_names: str) -> bool:
    """Test installing apps from catalog.

    Args:
        *app_names: Names of apps to install

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing catalog install: %s", ", ".join(app_names))
    result = run_cli("install", *app_names)
    return result.returncode == 0


def test_update(*app_names: str) -> bool:
    """Test updating apps.

    Args:
        *app_names: Names of apps to update

    Returns:
        True if successful, False otherwise
    """
    logger.info("Testing update for: %s", ", ".join(app_names))

    # Set old versions for update test
    for app_name in app_names:
        set_version(app_name, TEST_VERSION)

    result = run_cli("update", *app_names)
    return result.returncode == 0


# ======== Test Suites ========


class TestTracker:
    """Track test results."""

    def __init__(self) -> None:
        """Initialize test tracker."""
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.start_time = datetime.now(tz=UTC)

    def record(self, test_name: str, success: bool) -> None:
        """Record test result.

        Args:
            test_name: Name of the test
            success: Whether the test passed
        """
        self.total += 1
        if success:
            self.passed += 1
            logger.info("✓ %s PASSED", test_name)
        else:
            self.failed += 1
            logger.error("✗ %s FAILED", test_name)

    def summary(self) -> None:
        """Print test summary."""
        elapsed = datetime.now(tz=UTC) - self.start_time
        elapsed_str = str(elapsed).split(".")[0]

        logger.info("")
        logger.info("=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        logger.info("Total Tests:  %s", self.total)
        logger.info("Passed:       %s", self.passed)
        logger.info("Failed:       %s", self.failed)
        logger.info("Time Elapsed: %s", elapsed_str)
        logger.info("=" * 60)

        if self.failed > 0:
            logger.error("Some tests failed!")
        else:
            logger.info("All tests passed!")


def test_quick(tracker: TestTracker) -> None:
    """Run quick tests with qownnotes.

    Args:
        tracker: Test result tracker
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("Running Quick Tests (qownnotes)")
    logger.info("=" * 60)
    logger.info("")

    # Step 1: Remove qownnotes for clean state
    logger.info("Step 1/5: Removing qownnotes for clean URL install test")
    remove_apps("qownnotes")

    # Step 2: Test URL install
    logger.info("Step 2/5: Testing qownnotes URL install")
    result = test_url_install("qownnotes", "https://github.com/pbek/QOwnNotes")
    tracker.record("QOwnNotes URL install", result)

    # Step 3: Remove qownnotes for clean catalog test
    logger.info("Step 3/5: Removing qownnotes for clean catalog install test")
    remove_apps("qownnotes")

    # Step 4: Test catalog install
    logger.info("Step 4/5: Testing qownnotes catalog install")
    result = test_catalog_install("qownnotes")
    tracker.record("QOwnNotes catalog install", result)

    # Step 5: Test update
    logger.info("Step 5/5: Testing qownnotes update")
    result = test_update("qownnotes")
    tracker.record("QOwnNotes update", result)

    logger.info("")
    logger.info("Quick tests completed")


def test_all(tracker: TestTracker) -> None:
    """Run all comprehensive tests.

    Args:
        tracker: Test result tracker
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("Running All Comprehensive Tests")
    logger.info("=" * 60)
    logger.info("")

    # Test URL installs
    logger.info("--- Testing URL installs (neovim + keepassxc) ---")
    logger.info("Step 1/2: Removing apps for clean URL install test")
    remove_apps("neovim", "keepassxc")

    logger.info("Step 2/2: Testing concurrent URL installs")
    result = run_cli(
        "install",
        "https://github.com/neovim/neovim",
        "https://github.com/keepassxreboot/keepassxc",
    )
    tracker.record("URL installs (neovim + keepassxc)", result.returncode == 0)

    # Test catalog installs
    logger.info("")
    logger.info(
        "--- Testing catalog installs "
        "(legcord + flameshot + appflowy + standard-notes) ---"
    )
    logger.info("Step 1/2: Removing apps for clean catalog install test")
    remove_apps("legcord", "flameshot")

    logger.info("Step 2/2: Testing multiple catalog install")
    result = test_catalog_install(
        "legcord", "flameshot", "appflowy", "standard-notes"
    )
    tracker.record("Catalog installs (multiple apps)", result)

    # Test updates
    logger.info("")
    logger.info("--- Testing updates for multiple apps ---")
    result = test_update(
        "legcord", "flameshot", "keepassxc", "appflowy", "standard-notes"
    )
    tracker.record("Updates (multiple apps)", result)

    logger.info("")
    logger.info("All comprehensive tests completed")


# ======== Main Function ========


def init_test_environment() -> None:
    """Initialize test environment and logging."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("my-unicorn Comprehensive Testing")
    logger.info("=" * 60)
    logger.info("App Root:    %s", APP_ROOT)
    logger.info("Config Dir:  %s", CONFIG_DIR)
    logger.info("Log File:    %s", LOG_FILE)

    env_type = "container" if is_container() else "normal machine"
    logger.info("Environment: %s", env_type)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Comprehensive Manual Testing Script for my-unicorn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s --quick          Run quick tests (qownnotes only)
  %(prog)s --all            Run all comprehensive tests
  %(prog)s --debug --quick  Run quick tests with debug logging
        """,
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick tests (qownnotes: URL → catalog → update)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all comprehensive tests",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging(debug=args.debug)

    # Initialize environment
    init_test_environment()

    # Create test tracker
    tracker = TestTracker()

    # Run tests based on arguments
    try:
        if args.quick:
            test_quick(tracker)
        elif args.all:
            test_all(tracker)
        else:
            parser.print_help()
            return 0

        # Print summary
        tracker.summary()

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("Tests interrupted by user")
        return 130
    except Exception:
        logger.exception("Unexpected error")
        return 1
    else:
        return 0 if tracker.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
