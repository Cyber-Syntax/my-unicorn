#!/usr/bin/env python3
"""Cache utility functions.

This module provides common functionality for handling cache operations,
particularly for API rate limits and other data that needs to be persisted.
"""

import json
import logging
import os
import time
from typing import Any

# Configure module logger
logger = logging.getLogger(__name__)


def ensure_directory_exists(directory_path: str) -> str:
    """Ensure the specified directory exists, creating it if necessary.

    Args:
        directory_path: Path to directory to ensure exists

    Returns:
        str: Path to the directory

    """
    os.makedirs(directory_path, exist_ok=True)
    return directory_path


def load_json_cache(
    cache_file_path: str,
    ttl_seconds: int = 3600,
    hard_refresh_seconds: int | None = None,
) -> tuple[str, Any]:
    """Load cached data from a JSON file with TTL validation.

    Args:
        cache_file_path: Path to the cache file
        ttl_seconds: Time-to-live in seconds (default: 1 hour)
        hard_refresh_seconds: Optional longer TTL for stale data

    Returns:
        tuple[str, Any]: Cache data or empty dict if invalid/expired

    """
    try:
        if os.path.exists(cache_file_path):
            with open(cache_file_path) as f:
                data = json.load(f)

            # Check if cache is still valid
            current_time = time.time()
            cache_age = current_time - data.get("timestamp", 0)

            # Check primary TTL
            if cache_age < ttl_seconds:
                logger.debug("Using cache from %s (age: %ds)", cache_file_path, int(cache_age))
                return data

            # Check secondary TTL (hard refresh limit) if specified
            if hard_refresh_seconds and cache_age < hard_refresh_seconds:
                logger.debug(
                    "Using stale cache from %s (age: %ds)", cache_file_path, int(cache_age)
                )
                # Reset request counter but keep the data
                if "request_count" in data:
                    data["request_count"] = 0
                return data

            logger.debug("Cache expired: %s (age: %ds)", cache_file_path, int(cache_age))
        return {}
    except Exception as e:
        logger.debug("Error loading cache from %s: %s", cache_file_path, e)
        return {}


def save_json_cache(cache_file_path: str, data: tuple[str, Any]) -> bool:
    """Save data to a JSON cache file with atomic updates.

    Args:
        cache_file_path: Path to the cache file
        data: Data to cache

    Returns:
        bool: True if saved successfully, False otherwise

    """
    try:
        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = time.time()

        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(cache_file_path), exist_ok=True)

        # Use atomic write pattern with a temporary file
        temp_file = f"{cache_file_path}.tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f)

        # set permissions before atomic replace
        os.chmod(temp_file, 0o600)

        # Atomic replace
        os.replace(temp_file, cache_file_path)
        return True
    except Exception as e:
        logger.debug("Error saving cache to %s: %s", cache_file_path, e)

        # Try to clean up temp file if it exists
        try:
            if os.path.exists("%s.tmp" % cache_file_path):
                os.remove("%s.tmp" % cache_file_path)
        except:
            pass

        return False
