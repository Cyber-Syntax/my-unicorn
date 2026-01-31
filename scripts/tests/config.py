"""Configuration management utilities for my-unicorn testing.

This module provides functions to read and modify app configuration files
for testing purposes.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

import logging
from pathlib import Path
from typing import Any

import orjson

logger = logging.getLogger("my-unicorn-test")

# Configuration constants
CONFIG_DIR = Path.home() / ".config" / "my-unicorn"
APPS_DIR = CONFIG_DIR / "apps"


def set_version(app_name: str, version: str) -> bool:
    """Set app version in config file for update testing.

    Args:
        app_name: Name of the app
        version: Version to set

    Returns:
        True if successful, False otherwise
    """
    config_file = APPS_DIR / f"{app_name}.json"

    if not config_file.exists():
        logger.warning(
            "Config not found: %s; skipping version set", config_file
        )
        return False

    try:
        config = orjson.loads(config_file.read_bytes())

        config["state"]["version"] = version

        config_file.write_bytes(
            orjson.dumps(config, option=orjson.OPT_INDENT_2)
        )

        logger.info(
            "Set %s version to %s (for update test)", app_name, version
        )
    except Exception:
        logger.exception("Failed to set version for %s", app_name)
        return False
    else:
        return True


def load_app_config(app_name: str) -> dict[str, Any] | None:
    """Load app config file.

    Args:
        app_name: Name of the app

    Returns:
        Config dictionary or None if not found
    """
    config_file = APPS_DIR / f"{app_name}.json"
    if not config_file.exists():
        return None

    try:
        return orjson.loads(config_file.read_bytes())
    except Exception:
        logger.exception("Failed to load config for %s", app_name)
        return None
