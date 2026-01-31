"""Logging configuration for my-unicorn test suite.

This module sets up logging with console and file handlers
for comprehensive test execution tracking.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import logging
import sys
from pathlib import Path

# Configuration constants
CONFIG_DIR = Path.home() / ".config" / "my-unicorn"
LOG_DIR = CONFIG_DIR / "logs"
LOG_FILE = LOG_DIR / "comprehensive_test.log"


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
